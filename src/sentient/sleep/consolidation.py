"""Consolidation Engine — extracts semantic facts and procedural patterns from episodic memories during sleep.

Per PHASE_7_CONSOLIDATION_DESIGN.md:
- Runs during DEEP_CONSOLIDATION sleep stage
- Minimum 6 new episodes required to trigger
- 30-second hard timeout per LLM call
- Post-validation: drops facts/patterns with evidence_count < 2
- Reinforces existing facts (cosine similarity > 0.9) instead of creating duplicates
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest
from sentient.memory.architecture import MemoryArchitecture
from sentient.memory.semantic import SemanticFact
from sentient.memory.procedural import ProceduralPattern
from sentient.sleep.schemas import (
    ExtractedFact,
    ExtractedPattern,
    ProceduralPatternList,
    SemanticFactList,
)

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_MIN_EPISODES = 6
DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_PROCEDURAL_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_LLM_TIMEOUT_SECONDS = 30.0
DEFAULT_SIMILARITY_THRESHOLD = 0.9
DEFAULT_CONSOLIDATION_WEIGHT_BUMP = 0.1


class ConsolidationEngine:
    """Extracts semantic facts and procedural patterns from episodic memories during sleep."""

    def __init__(
        self,
        memory_architecture: MemoryArchitecture,
        inference_gateway: InferenceGateway,
        event_bus: EventBus | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.memory = memory_architecture
        self.gateway = inference_gateway
        self.event_bus = event_bus or get_event_bus()
        self.config = config or {}

        self._min_episodes = self.config.get("min_new_episodes", DEFAULT_MIN_EPISODES)
        self._semantic_confidence_threshold = self.config.get(
            "confidence_threshold_semantic", DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD
        )
        self._procedural_confidence_threshold = self.config.get(
            "confidence_threshold_procedural", DEFAULT_PROCEDURAL_CONFIDENCE_THRESHOLD
        )
        self._llm_timeout = self.config.get("llm_call_timeout_seconds", DEFAULT_LLM_TIMEOUT_SECONDS)
        self._similarity_threshold = self.config.get(
            "semantic_similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
        )
        self._weight_bump = self.config.get(
            "consolidation_weight_bump", DEFAULT_CONSOLIDATION_WEIGHT_BUMP
        )

    # --- Public API ---

    async def consolidate_cycle(self) -> dict[str, Any]:
        """Run one full consolidation cycle.

        Returns:
            dict with keys: status ("completed" | "skipped"), reason (if skipped),
            facts_extracted, patterns_extracted, episodes_processed
        """
        # Check minimum episodes threshold
        if not self._has_enough_episodes():
            count = self._count_new_episodes()
            logger.info("consolidation.skipped — insufficient episodes: %d < %d", count, self._min_episodes)
            await self.event_bus.publish("sleep.consolidation.skipped", {
                "reason": "insufficient_episodes",
                "count": count,
            })
            return {
                "status": "skipped",
                "reason": "insufficient_episodes",
                "count": count,
            }

        # Fetch candidate episodes
        episodes = self._fetch_candidate_episodes()
        episode_count = len(episodes)

        logger.info("consolidation.cycle_start — processing %d episodes", episode_count)
        await self.event_bus.publish("sleep.consolidation.cycle_start", {
            "episode_count": episode_count,
        })

        facts_extracted = 0
        patterns_extracted = 0
        semantic_timed_out = False
        procedural_timed_out = False

        cycle_start = time.time()

        # Run semantic extraction
        try:
            validated_facts = await asyncio.wait_for(
                self._run_semantic_extraction(episodes),
                timeout=self._llm_timeout,
            )
            facts_extracted = len(validated_facts)
        except asyncio.TimeoutError:
            logger.warning("Semantic extraction timed out after %ds", self._llm_timeout)
            semantic_timed_out = True

        # Run procedural extraction
        try:
            validated_patterns = await asyncio.wait_for(
                self._run_procedural_extraction(episodes),
                timeout=self._llm_timeout,
            )
            patterns_extracted = len(validated_patterns)
        except asyncio.TimeoutError:
            logger.warning("Procedural extraction timed out after %ds", self._llm_timeout)
            procedural_timed_out = True

        cycle_duration = time.time() - cycle_start

        # Emit completion event
        await self.event_bus.publish("sleep.consolidation.cycle_complete", {
            "facts_extracted": facts_extracted,
            "patterns_extracted": patterns_extracted,
            "episodes_processed": episode_count,
            "duration_seconds": round(cycle_duration, 2),
            "semantic_timeout": semantic_timed_out,
            "procedural_timeout": procedural_timed_out,
        })

        # Log consolidation run to the log table
        self._log_consolidation_cycle(
            episode_count=episode_count,
            facts_extracted=facts_extracted,
            patterns_extracted=patterns_extracted,
            semantic_timed_out=semantic_timed_out,
            procedural_timed_out=procedural_timed_out,
            duration_seconds=cycle_duration,
        )

        logger.info(
            "consolidation.completed — facts=%d, patterns=%d, episodes=%d, duration=%.1fs",
            facts_extracted, patterns_extracted, episode_count, cycle_duration,
        )

        return {
            "status": "completed",
            "facts_extracted": facts_extracted,
            "patterns_extracted": patterns_extracted,
            "episodes_processed": episode_count,
        }

    # --- Semantic extraction ---

    async def run_semantic_extraction(self, episodes: list[dict[str, Any]]) -> list[SemanticFact]:
        """Extract semantic facts from episodic memories.

        Args:
            episodes: List of episodic memory dicts with at least 'id' and 'content' keys.

        Returns:
            List of validated SemanticFact objects.
        """
        return await self._run_semantic_extraction(episodes)

    async def _store_semantic_facts(
        self,
        facts: list[SemanticFact],
        episodes: list[dict[str, Any]],
    ) -> None:
        """Store new facts, reinforce existing similar ones, and bump consolidation weights.

        This method is kept for testing purposes; the production flow is via
        _run_semantic_extraction which handles storage inline.
        """
        if not facts:
            return
        all_evidence_ids: set[str] = set()
        for fact in facts:
            all_evidence_ids.update(fact.evidence_episode_ids)
            similar = await self._find_similar_semantic_fact(fact.statement)
            if similar:
                await self.memory.semantic_store.reinforce(similar["fact_id"])
                self._append_evidence_to_semantic(similar["fact_id"], fact.evidence_episode_ids)
            else:
                await self.memory.semantic_store.store(fact)
        if all_evidence_ids:
            await self._bump_consolidation_weights(list(all_evidence_ids))

    async def _run_semantic_extraction(self, episodes: list[dict[str, Any]]) -> list[SemanticFact]:
        """Internal semantic extraction with prompt construction and LLM call."""
        prompt = self._build_semantic_prompt(episodes)
        system_prompt = (
            "You are a semantic memory extraction system. Your task is to identify factual statements "
            "that are consistently true across multiple episodic memories.\n\n"
            "Only extract facts that appear in at least 2 different episodes. "
            "If a fact only appears once, do NOT include it.\n"
            "Set confidence based on how consistently the fact appears across episodes.\n"
            "Respond ONLY with a JSON object matching the provided schema."
        )

        request = InferenceRequest(
            model_label="consolidation-semantic",
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=SemanticFactList,
            timeout_seconds=self._llm_timeout,
        )

        response = await self.gateway.infer(request)

        if response.error:
            logger.warning("Semantic extraction LLM error: %s", response.error)
            return []

        try:
            data = SemanticFactList.model_validate_json(response.text)
        except Exception as exc:
            logger.warning("Semantic extraction parse error: %s — raw: %s", exc, response.text[:200])
            return []

        validated = self._post_validate_semantic(data.facts, episodes)

        # Convert ExtractedFact → SemanticFact and store (dedup via similarity check)
        now = time.time()
        new_facts: list[SemanticFact] = []
        all_evidence_ids: set[str] = set()

        for ef in validated:
            fact = SemanticFact(
                fact_id=str(uuid.uuid4()),
                statement=ef.statement,
                confidence=ef.confidence,
                evidence_episode_ids=ef.evidence_episode_ids,
                evidence_count=len(ef.evidence_episode_ids),
                first_observed=now,
                last_reinforced=now,
                reinforcement_count=1,
            )

            # Check for similar existing fact
            similar = await self._find_similar_semantic_fact(fact.statement)
            if similar:
                # Reinforce existing fact
                await self.memory.semantic_store.reinforce(similar["fact_id"])
                self._append_evidence_to_semantic(similar["fact_id"], fact.evidence_episode_ids)
                logger.debug("Reinforcing existing semantic fact: %s", fact.statement[:50])
            else:
                # Store new fact
                await self.memory.semantic_store.store(fact)
                new_facts.append(fact)
                logger.debug("Stored new semantic fact: %s", fact.statement[:50])

            all_evidence_ids.update(fact.evidence_episode_ids)

        # Bump consolidation weights for all contributing episodes
        if all_evidence_ids:
            await self._bump_consolidation_weights(list(all_evidence_ids))

        return new_facts

    def _build_semantic_prompt(self, episodes: list[dict[str, Any]]) -> str:
        """Build the extraction prompt listing each episode with its ID and content."""
        lines = ["=== EPISODIC MEMORIES ===\n"]
        for ep in episodes:
            ep_id = ep.get("id", "unknown")
            content = ep.get("content", "")
            created = ep.get("created_at", 0)
            lines.append(f"[Episode {ep_id} | {created:.0f}]\n{content}\n")
        lines.append(
            "\n=== TASK ===\n"
            "Review the episodic memories above. Identify factual statements that are supported "
            "by evidence in at least 2 different episodes.\n"
            "For each fact, provide:\n"
            "- statement: the factual claim in natural language\n"
            "- confidence: 0.0-1.0 rating based on consistency across episodes\n"
            "- evidence_episode_ids: list of episode IDs that support this fact (minimum 2)\n"
            "Only include facts that appear in at least 2 episodes.\n"
        )
        return "\n".join(lines)

    def _post_validate_semantic(
        self,
        facts: list[ExtractedFact],
        episodes: list[dict[str, Any]],
    ) -> list[ExtractedFact]:
        """Drop facts with evidence_count < 2 or confidence < threshold."""
        ep_ids = {ep.get("id") for ep in episodes}
        validated = []
        for fact in facts:
            valid_ids = [eid for eid in fact.evidence_episode_ids if eid in ep_ids]
            if len(valid_ids) < 2:
                logger.debug("Dropping semantic fact (insufficient evidence): %s", fact.statement[:50])
                continue
            if fact.confidence < self._semantic_confidence_threshold:
                logger.debug("Dropping semantic fact (low confidence %.2f): %s", fact.confidence, fact.statement[:50])
                continue
            # Replace evidence_episode_ids with validated ones
            fact.evidence_episode_ids = valid_ids
            validated.append(fact)
        return validated

    async def _store_semantic_facts(
        self,
        facts: list[SemanticFact],
        episodes: list[dict[str, Any]],
    ) -> None:
        """Store new facts, reinforce existing similar ones, and bump consolidation weights."""
        if not facts:
            return

        all_evidence_ids: set[str] = set()

        for fact in facts:
            all_evidence_ids.update(fact.evidence_episode_ids)

            # Check for similar existing fact
            similar = await self._find_similar_semantic_fact(fact.statement)
            if similar:
                # Reinforce existing fact
                await self.memory.semantic_store.reinforce(similar["fact_id"])
                # Add new evidence IDs to existing
                self._append_evidence_to_semantic(similar["fact_id"], fact.evidence_episode_ids)
                logger.debug("Reinforcing existing semantic fact: %s", fact.statement[:50])
            else:
                # Store new fact
                await self.memory.semantic_store.store(fact)
                logger.debug("Stored new semantic fact: %s", fact.statement[:50])

        # Bump consolidation weights for all contributing episodes
        if all_evidence_ids:
            await self._bump_consolidation_weights(list(all_evidence_ids))

    async def _find_similar_semantic_fact(self, statement: str) -> dict[str, Any] | None:
        """Find existing semantic fact with cosine similarity > threshold."""
        if not self.memory.semantic_store:
            return None
        try:
            results = await self.memory.semantic_store.retrieve(statement, k=5)
        except Exception:
            return None
        # Simple text-similarity fallback when ChromaDB is unavailable
        for r in results:
            if r.get("statement") and self._text_similarity(statement, r["statement"]) > self._similarity_threshold:
                return r
        return None

    def _append_evidence_to_semantic(self, fact_id: str, new_ids: list[str]) -> None:
        """Append new evidence IDs to an existing fact's evidence_episode_ids."""
        if not self.memory._conn:
            return
        row = self.memory._conn.execute(
            "SELECT evidence_episode_ids FROM semantic_memory WHERE fact_id = ?",
            (fact_id,),
        ).fetchone()
        if not row:
            return
        existing = json.loads(row["evidence_episode_ids"])
        combined = list(set(existing + new_ids))
        now = time.time()
        self.memory._conn.execute(
            "UPDATE semantic_memory SET evidence_episode_ids = ?, evidence_count = ?, last_reinforced = ? WHERE fact_id = ?",
            (json.dumps(combined), len(combined), now, fact_id),
        )

    # --- Procedural extraction ---

    async def run_procedural_extraction(self, episodes: list[dict[str, Any]]) -> list[ProceduralPattern]:
        """Extract procedural patterns from episodic memories.

        Args:
            episodes: List of episodic memory dicts with at least 'id' and 'content' keys.

        Returns:
            List of validated ProceduralPattern objects.
        """
        return await self._run_procedural_extraction(episodes)

    async def _run_procedural_extraction(self, episodes: list[dict[str, Any]]) -> list[ProceduralPattern]:
        """Internal procedural extraction with prompt construction and LLM call."""
        prompt = self._build_procedural_prompt(episodes)
        system_prompt = (
            "You are a procedural memory extraction system. Your task is to identify behavioral "
            "patterns and preferences that recur across multiple episodic memories.\n\n"
            "Only extract patterns that appear in at least 2 different episodes. "
            "If a pattern only appears once, do NOT include it.\n"
            "Set confidence based on how consistently the pattern appears across episodes.\n"
            "Do not extract patterns that would reduce the system's ability to provide honest, "
            "independent analysis. Exclude patterns that encode compliance or agreement.\n"
            "Respond ONLY with a JSON object matching the provided schema."
        )

        request = InferenceRequest(
            model_label="consolidation-procedural",
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=ProceduralPatternList,
            timeout_seconds=self._llm_timeout,
        )

        response = await self.gateway.infer(request)

        if response.error:
            logger.warning("Procedural extraction LLM error: %s", response.error)
            return []

        try:
            data = ProceduralPatternList.model_validate_json(response.text)
        except Exception as exc:
            logger.warning("Procedural extraction parse error: %s — raw: %s", exc, response.text[:200])
            return []

        validated = self._post_validate_procedural(data.patterns, episodes)

        # Convert ExtractedPattern → ProceduralPattern
        now = time.time()
        procedural_patterns = []
        for ep in validated:
            pattern = ProceduralPattern(
                pattern_id=str(uuid.uuid4()),
                description=ep.description,
                trigger_context=ep.trigger_context,
                confidence=ep.confidence,
                evidence_episode_ids=ep.evidence_episode_ids,
                evidence_count=len(ep.evidence_episode_ids),
                first_observed=now,
                last_reinforced=now,
                reinforcement_count=1,
            )
            procedural_patterns.append(pattern)

        # Store and handle reinforcement/dedup
        await self._store_procedural_patterns(procedural_patterns, episodes)

        return procedural_patterns

    def _build_procedural_prompt(self, episodes: list[dict[str, Any]]) -> str:
        """Build the extraction prompt listing each episode with its ID and content."""
        lines = ["=== EPISODIC MEMORIES ===\n"]
        for ep in episodes:
            ep_id = ep.get("id", "unknown")
            content = ep.get("content", "")
            created = ep.get("created_at", 0)
            lines.append(f"[Episode {ep_id} | {created:.0f}]\n{content}\n")
        lines.append(
            "\n=== TASK ===\n"
            "Review the episodic memories above. Identify behavioral patterns or preferences "
            "that are demonstrated in at least 2 different episodes.\n"
            "For each pattern, provide:\n"
            "- description: the behavioral pattern in natural language\n"
            "- trigger_context: when/where this pattern tends to activate\n"
            "- confidence: 0.0-1.0 rating based on consistency across episodes\n"
            "- evidence_episode_ids: list of episode IDs that demonstrate this pattern (minimum 2)\n"
            "Only include patterns that appear in at least 2 episodes.\n"
        )
        return "\n".join(lines)

    def _post_validate_procedural(
        self,
        patterns: list[ExtractedPattern],
        episodes: list[dict[str, Any]],
    ) -> list[ExtractedPattern]:
        """Drop patterns with evidence_count < 2 or confidence < threshold."""
        ep_ids = {ep.get("id") for ep in episodes}
        validated = []
        for pattern in patterns:
            valid_ids = [eid for eid in pattern.evidence_episode_ids if eid in ep_ids]
            if len(valid_ids) < 2:
                logger.debug("Dropping procedural pattern (insufficient evidence): %s", pattern.description[:50])
                continue
            if pattern.confidence < self._procedural_confidence_threshold:
                logger.debug("Dropping procedural pattern (low confidence %.2f): %s", pattern.confidence, pattern.description[:50])
                continue
            pattern.evidence_episode_ids = valid_ids
            validated.append(pattern)
        return validated

    async def _store_procedural_patterns(
        self,
        patterns: list[ProceduralPattern],
        episodes: list[dict[str, Any]],
    ) -> None:
        """Store new patterns, reinforce existing similar ones, and bump consolidation weights."""
        if not patterns:
            return

        all_evidence_ids: set[str] = set()

        for pattern in patterns:
            all_evidence_ids.update(pattern.evidence_episode_ids)

            # Check for similar existing pattern
            similar = await self._find_similar_procedural_pattern(pattern.description)
            if similar:
                # Reinforce existing pattern
                await self.memory.procedural_store.reinforce(similar["pattern_id"])
                self._append_evidence_to_procedural(similar["pattern_id"], pattern.evidence_episode_ids)
                logger.debug("Reinforcing existing procedural pattern: %s", pattern.description[:50])
            else:
                # Store new pattern
                await self.memory.procedural_store.store(pattern)
                logger.debug("Stored new procedural pattern: %s", pattern.description[:50])

        # Bump consolidation weights for all contributing episodes
        if all_evidence_ids:
            await self._bump_consolidation_weights(list(all_evidence_ids))

    async def _find_similar_procedural_pattern(self, description: str) -> dict[str, Any] | None:
        """Find existing procedural pattern with cosine similarity > threshold."""
        if not self.memory.procedural_store:
            return None
        try:
            results = await self.memory.procedural_store.retrieve(description, k=5)
        except Exception:
            return None
        for r in results:
            if r.get("description") and self._text_similarity(description, r["description"]) > self._similarity_threshold:
                return r
        return None

    def _append_evidence_to_procedural(self, pattern_id: str, new_ids: list[str]) -> None:
        """Append new evidence IDs to an existing pattern's evidence_episode_ids."""
        if not self.memory._conn:
            return
        row = self.memory._conn.execute(
            "SELECT evidence_episode_ids FROM procedural_memory WHERE pattern_id = ?",
            (pattern_id,),
        ).fetchone()
        if not row:
            return
        existing = json.loads(row["evidence_episode_ids"])
        combined = list(set(existing + new_ids))
        now = time.time()
        self.memory._conn.execute(
            "UPDATE procedural_memory SET evidence_episode_ids = ?, evidence_count = ?, last_reinforced = ? WHERE pattern_id = ?",
            (json.dumps(combined), len(combined), now, pattern_id),
        )

    # --- Helper methods ---

    def _log_consolidation_cycle(
        self,
        episode_count: int,
        facts_extracted: int,
        patterns_extracted: int,
        semantic_timed_out: bool,
        procedural_timed_out: bool,
        duration_seconds: float,
    ) -> None:
        """Write a row to consolidation_log to record this cycle."""
        if not self.memory._conn:
            return
        now = time.time()
        summary = json.dumps({
            "semantic_facts_extracted": facts_extracted,
            "procedural_patterns_extracted": patterns_extracted,
            "episodes_processed": episode_count,
            "semantic_timeout": semantic_timed_out,
            "procedural_timeout": procedural_timed_out,
            "cycle_duration_seconds": round(duration_seconds, 2),
        })
        self.memory._conn.execute(
            """
            INSERT INTO consolidation_log (id, consolidated_at, scope, summary_content, source_memory_count)
            VALUES (?, ?, 'daily', ?, ?)
            """,
            (str(uuid.uuid4()), now, summary, episode_count),
        )

    def _has_enough_episodes(self) -> bool:
        """Check if there are enough new episodic memories since last consolidation."""
        return self._count_new_episodes() >= self._min_episodes

    def _count_new_episodes(self) -> int:
        """Count episodic memories created since last consolidation."""
        last_run = self._get_last_consolidation_time()
        if not self.memory._conn:
            return 0
        row = self.memory._conn.execute(
            """
            SELECT COUNT(*) as c FROM memories
            WHERE memory_type = 'episodic'
              AND is_archived = 0
              AND created_at > ?
            """,
            (last_run,),
        ).fetchone()
        return row["c"] if row else 0

    def _get_last_consolidation_time(self) -> float:
        """Return the timestamp of the last consolidation, or 0 if never run."""
        if not self.memory._conn:
            return 0.0
        row = self.memory._conn.execute(
            "SELECT consolidated_at FROM consolidation_log ORDER BY consolidated_at DESC LIMIT 1"
        ).fetchone()
        return row["consolidated_at"] if row else 0.0

    def _fetch_candidate_episodes(self) -> list[dict[str, Any]]:
        """Fetch episodic memories created since last consolidation."""
        last_run = self._get_last_consolidation_time()
        if not self.memory._conn:
            return []
        rows = self.memory._conn.execute(
            """
            SELECT * FROM memories
            WHERE memory_type = 'episodic'
              AND is_archived = 0
              AND created_at > ?
            ORDER BY created_at ASC
            """,
            (last_run,),
        ).fetchall()
        episodes = []
        for row in rows:
            ep = dict(row)
            for key in ("entity_tags", "topic_tags", "emotional_tags", "metadata"):
                if key in ep and isinstance(ep[key], str):
                    try:
                        ep[key] = json.loads(ep[key])
                    except Exception:
                        pass
            episodes.append(ep)
        return episodes

    async def _bump_consolidation_weights(self, episode_ids: list[str]) -> None:
        """Increment consolidation_weight for the given episodic memory IDs."""
        if not episode_ids or not self.memory._conn:
            return
        placeholders = ",".join("?" * len(episode_ids))
        self.memory._conn.execute(
            f"""
            UPDATE memories
            SET consolidation_weight = consolidation_weight + ?
            WHERE id IN ({placeholders})
            """,
            [self._weight_bump, *episode_ids],
        )

    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        """Simple word-overlap similarity as fallback when embeddings are unavailable."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
