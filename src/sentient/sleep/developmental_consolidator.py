"""Developmental Consolidator — extracts personality signals from episodic and semantic memories during sleep.

Per Phase 9 D6:
  - Runs during DEEP_CONSOLIDATION sleep stage
  - Fetches recent episodic and semantic memories from memory store
  - Uses LLM to identify personality signals with >= min_evidence_points
  - Caps output at max_traits_per_cycle
  - Publishes sleep.consolidation.developmental event with updates payload
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest
from sentient.memory.architecture import MemoryArchitecture

if TYPE_CHECKING:
    from sentient.persona.identity_manager import PersonaManager

logger = logging.getLogger(__name__)

# Default config values
DEFAULT_ENABLED = True
DEFAULT_MIN_EVIDENCE_POINTS = 3
DEFAULT_MAX_TRAITS_PER_CYCLE = 5
DEFAULT_LLM_TIMEOUT_SECONDS = 30.0


class DevelopmentalConsolidator:
    """Extracts personality signals from episodic and semantic memories during sleep."""

    def __init__(
        self,
        memory: MemoryArchitecture,
        gateway: InferenceGateway,
        persona: "PersonaManager",
        event_bus: EventBus | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.memory = memory
        self.gateway = gateway
        self.persona = persona
        self.event_bus = event_bus or get_event_bus()
        self.config = config or {}

        self._enabled = self.config.get("enabled", DEFAULT_ENABLED)
        self._min_evidence_points = self.config.get(
            "min_evidence_points", DEFAULT_MIN_EVIDENCE_POINTS
        )
        self._max_traits_per_cycle = self.config.get(
            "max_traits_per_cycle", DEFAULT_MAX_TRAITS_PER_CYCLE
        )
        self._llm_timeout = self.config.get(
            "llm_timeout_seconds", DEFAULT_LLM_TIMEOUT_SECONDS
        )

    # --- Public API ---

    async def consolidate(self) -> dict[str, Any]:
        """Run one developmental consolidation cycle.

        Returns:
            dict with keys: signals_extracted, traits_proposed, traits_applied
        """
        if not self._enabled:
            logger.info("Developmental consolidation disabled — skipping")
            return {
                "signals_extracted": 0,
                "traits_proposed": 0,
                "traits_applied": 0,
                "status": "skipped",
                "reason": "disabled",
            }

        # Fetch recent memories
        episodic_memories = self._fetch_episodic_memories()
        semantic_facts = self._fetch_semantic_facts()

        if not episodic_memories:
            logger.info("Developmental consolidation: no episodic memories found — skipping")
            return {
                "signals_extracted": 0,
                "traits_proposed": 0,
                "traits_applied": 0,
                "status": "skipped",
                "reason": "no_memories",
            }

        episodic_content = self._format_episodic(episodic_memories)
        semantic_content = self._format_semantic(semantic_facts)

        # Build LLM prompt
        prompt = self._build_prompt(episodic_content, semantic_content)

        # Call LLM
        try:
            signals = await asyncio.wait_for(
                self._extract_signals(prompt),
                timeout=self._llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Developmental consolidation LLM call timed out after %ds",
                self._llm_timeout,
            )
            return {
                "signals_extracted": 0,
                "traits_proposed": 0,
                "traits_applied": 0,
                "status": "error",
                "reason": "llm_timeout",
            }

        # Filter by min_evidence_points
        filtered = [s for s in signals if s.get("evidence_count", 0) >= self._min_evidence_points]
        logger.info(
            "Developmental consolidation: %d signals extracted, %d after evidence filter",
            len(signals),
            len(filtered),
        )

        # Cap at max_traits_per_cycle
        proposed = filtered[: self._max_traits_per_cycle]
        traits_proposed = len(proposed)

        # Build updates payload
        updates = self._build_updates(proposed)
        traits_applied = sum(
            len(v) if isinstance(v, dict) else len(v) if isinstance(v, list) else 0
            for v in updates.values()
        )

        # Publish event
        await self.event_bus.publish(
            "sleep.consolidation.developmental",
            {"updates": updates},
        )

        logger.info(
            "Developmental consolidation: proposed=%d, applied=%d",
            traits_proposed,
            traits_applied,
        )

        return {
            "signals_extracted": len(signals),
            "traits_proposed": traits_proposed,
            "traits_applied": traits_applied,
            "status": "completed",
        }

    # --- Memory fetching ---

    def _fetch_episodic_memories(self) -> list[dict[str, Any]]:
        """Fetch recent episodic memories from SQLite."""
        if not self.memory._conn:
            return []
        cutoff = time.time() - (7 * 86400)  # Last 7 days
        rows = self.memory._conn.execute(
            """
            SELECT * FROM memories
            WHERE memory_type = 'episodic'
              AND is_archived = 0
              AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (cutoff,),
        ).fetchall()
        memories = []
        for row in rows:
            ep = dict(row)
            for key in ("entity_tags", "topic_tags", "emotional_tags", "metadata"):
                if key in ep and isinstance(ep[key], str):
                    try:
                        ep[key] = json.loads(ep[key])
                    except Exception:
                        pass
            memories.append(ep)
        return memories

    def _fetch_semantic_facts(self) -> list[dict[str, Any]]:
        """Fetch recent semantic facts from SQLite."""
        if not self.memory._conn:
            return []
        rows = self.memory._conn.execute(
            """
            SELECT * FROM semantic_memory
            ORDER BY last_reinforced DESC
            LIMIT 50
            """,
        ).fetchall()
        return [dict(row) for row in rows]

    # --- Prompt building ---

    def _build_prompt(self, episodic_content: str, semantic_content: str) -> str:
        """Build the LLM extraction prompt."""
        return f"""You are analyzing episodic and semantic memories to identify personality signals — observable patterns in how the entity behaves, communicates, and relates to its creator.

EPISODIC MEMORIES:
{episodic_content}

SEMANTIC FACTS:
{semantic_content}

Identify personality signals that are supported by at least 3 different pieces of evidence. For each signal, provide:
- trait_name: a short trait name (e.g., "curiosity", "cautiousness", "expressiveness")
- strength: 0.0-1.0 based on consistency and frequency
- evidence_count: how many memories support this
- evidence_descriptions: brief description of supporting evidence (list of strings)
- category: one of "personality_traits", "communication_style", "interests", "self_understanding", "relational_texture"

Respond ONLY with JSON: {{"signals": [...]}}"""

    def _format_episodic(self, memories: list[dict[str, Any]]) -> str:
        """Format episodic memories for the prompt."""
        if not memories:
            return "No episodic memories available."
        lines = []
        for ep in memories[:20]:  # Limit to 20 most recent
            ep_id = ep.get("id", "unknown")
            content = ep.get("content", "")
            created = ep.get("created_at", 0)
            lines.append(f"[Episode {ep_id} | {created:.0f}]\n{content}\n")
        return "\n".join(lines)

    def _format_semantic(self, facts: list[dict[str, Any]]) -> str:
        """Format semantic facts for the prompt."""
        if not facts:
            return "No semantic facts available."
        lines = []
        for fact in facts[:20]:  # Limit to 20 most recent
            statement = fact.get("statement", "")
            confidence = fact.get("confidence", 0)
            lines.append(f"- [{confidence:.2f}] {statement}")
        return "\n".join(lines)

    # --- LLM extraction ---

    async def _extract_signals(self, prompt: str) -> list[dict[str, Any]]:
        """Call LLM to extract personality signals from memories."""
        from sentient.core.inference_gateway import _strip_markdown_fences

        request = InferenceRequest(
            model_label="consolidation-semantic",
            prompt=prompt,
            system_prompt=(
                "You are a personality signal extraction system. Identify observable "
                "behavioral and communication patterns from episodic and semantic memories. "
                "Respond ONLY with valid JSON matching the specified schema."
            ),
            timeout_seconds=self._llm_timeout,
        )

        response = await self.gateway.infer(request)

        if response.error:
            logger.warning("Developmental consolidation LLM error: %s", response.error)
            return []

        raw_text = _strip_markdown_fences(response.text)

        try:
            data = json.loads(raw_text)
            signals = data.get("signals", [])
            return signals
        except json.JSONDecodeError as exc:
            logger.warning(
                "Developmental consolidation parse error: %s — raw: %s",
                exc,
                response.text[:200],
            )
            return []

    # --- Updates building ---

    def _build_updates(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        """Convert LLM signals into updates payload structure."""
        updates: dict[str, Any] = {
            "personality_traits": {},
            "communication_style": {},
            "interests": [],
            "self_understanding": {},
            "relational_texture": {"creator": {}},
        }

        for signal in signals:
            category = signal.get("category", "")
            trait_name = signal.get("trait_name", "")
            if not trait_name:
                continue

            if category == "personality_traits":
                updates["personality_traits"][trait_name] = {
                    "strength": signal.get("strength", 0.5),
                    "evidence_count": signal.get("evidence_count", 0),
                    "evidence_descriptions": signal.get("evidence_descriptions", []),
                }
            elif category == "communication_style":
                updates["communication_style"][trait_name] = {
                    "strength": signal.get("strength", 0.5),
                    "evidence_count": signal.get("evidence_count", 0),
                    "evidence_descriptions": signal.get("evidence_descriptions", []),
                }
            elif category == "interests":
                if trait_name not in updates["interests"]:
                    updates["interests"].append(trait_name)
            elif category == "self_understanding":
                if "capabilities_recognized" not in updates["self_understanding"]:
                    updates["self_understanding"]["capabilities_recognized"] = []
                if trait_name not in updates["self_understanding"]["capabilities_recognized"]:
                    updates["self_understanding"]["capabilities_recognized"].append(trait_name)
            elif category == "relational_texture":
                if "creator" not in updates["relational_texture"]:
                    updates["relational_texture"]["creator"] = {}
                updates["relational_texture"]["creator"][trait_name] = {
                    "strength": signal.get("strength", 0.5),
                    "evidence_count": signal.get("evidence_count", 0),
                    "evidence_descriptions": signal.get("evidence_descriptions", []),
                }

        # Remove empty categories
        return {k: v for k, v in updates.items() if v and (not isinstance(v, dict) or v)}
