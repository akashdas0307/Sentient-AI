"""Contradiction Resolver — detects and resolves contradictory memories during sleep consolidation.

Job 2 of the four-stage sleep consolidation pipeline (ARCHITECTURE.md §3.5):
  - Fetches recent episodic memories
  - Computes pairwise Jaccard similarity on extracted claims
  - Filters pairs with contradicting signals (negation words, antonyms)
  - Confirms contradictions via LLM call with 30s timeout
  - Writes resolutions to contradictions table, lowers confidence of superseded memory

Per Phase 9 D4 spec.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest
from sentient.core.inference_gateway import _strip_markdown_fences
from sentient.memory.architecture import MemoryArchitecture

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_ENABLED = True
DEFAULT_MAX_PAIRS_PER_CYCLE = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.3
DEFAULT_LLM_TIMEOUT_SECONDS = 30.0

# Negation / contradiction signal words
_NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "none", "nothing",
    "wasn't", "weren't", "isn't", "aren't", "wasn't", "weren't",
    "didn't", "don't", "doesn't", "didn't",
    "can't", "couldn't", "won't", "wouldn't", "shouldn't",
    "couldn't", "cannot",
    "but", "however", "although", "though", "yet",
}

# Simple antonym pairs for contradiction detection
_ANTONYMS = {
    "good": "bad", "bad": "good",
    "yes": "no", "no": "yes",
    "true": "false", "false": "true",
    "hot": "cold", "cold": "hot",
    "big": "small", "small": "big",
    "right": "wrong", "wrong": "right",
    "in": "out", "out": "in",
    "positive": "negative", "negative": "positive",
    "increase": "decrease", "decrease": "increase",
    "safe": "dangerous", "dangerous": "safe",
    "fast": "slow", "slow": "fast",
    "like": "dislike", "dislike": "like",
}


class ContradictionResolver:
    """Detects and resolves contradictory episodic memories during sleep consolidation."""

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

        self._enabled = self.config.get("enabled", DEFAULT_ENABLED)
        self._max_pairs_per_cycle = self.config.get(
            "max_pairs_per_cycle", DEFAULT_MAX_PAIRS_PER_CYCLE
        )
        self._similarity_threshold = self.config.get(
            "similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
        )
        self._llm_timeout = self.config.get(
            "llm_timeout_seconds", DEFAULT_LLM_TIMEOUT_SECONDS
        )

    # --- Public API ---

    async def resolve_contradictions(self) -> dict[str, Any]:
        """Run one cycle of contradiction detection and resolution.

        Returns:
            dict with keys: pairs_checked, contradictions_found, resolutions, status
        """
        if not self._enabled:
            logger.info("Contradiction resolver disabled — skipping")
            return {"status": "skipped", "reason": "disabled"}

        logger.info("Contradiction resolver: starting cycle")
        await self.event_bus.publish(
            "sleep.consolidation.contradiction_resolver.start",
            {},
        )

        # 1. Fetch recent episodic memories
        episodes = self._fetch_recent_episodes()
        if len(episodes) < 2:
            logger.info("Contradiction resolver: insufficient episodes (need ≥2, got %d)", len(episodes))
            return {"status": "completed", "pairs_checked": 0, "contradictions_found": 0, "resolutions": []}

        # 2. Generate candidate pairs using Jaccard similarity + contradiction signals
        candidates = self._generate_candidate_pairs(episodes)
        if not candidates:
            logger.info("Contradiction resolver: no candidate pairs found")
            return {"status": "completed", "pairs_checked": 0, "contradictions_found": 0, "resolutions": []}

        # 3. Limit to max_pairs_per_cycle
        candidates = candidates[:self._max_pairs_per_cycle]

        # 4. Check each candidate pair via LLM
        resolutions = []
        contradictions_found = 0

        for memory_a, memory_b in candidates:
            result = await self._check_pair(memory_a, memory_b)
            if result["contradicts"]:
                contradictions_found += 1
                resolution = self._record_resolution(memory_a, memory_b, result)
                resolutions.append(resolution)
                await self.event_bus.publish(
                    "sleep.consolidation.contradiction_resolved",
                    {
                        "memory_a_id": memory_a["id"],
                        "memory_b_id": memory_b["id"],
                        "resolution": result.get("resolution"),
                        "notes": result.get("notes"),
                    },
                )

        logger.info(
            "Contradiction resolver: checked %d pairs, found %d contradictions, resolved %d",
            len(candidates), contradictions_found, len(resolutions),
        )

        await self.event_bus.publish(
            "sleep.consolidation.contradiction_resolver.complete",
            {
                "pairs_checked": len(candidates),
                "contradictions_found": contradictions_found,
                "resolutions_count": len(resolutions),
            },
        )

        return {
            "status": "completed",
            "pairs_checked": len(candidates),
            "contradictions_found": contradictions_found,
            "resolutions": resolutions,
        }

    # --- Private helpers ---

    def _fetch_recent_episodes(self) -> list[dict[str, Any]]:
        """Fetch episodic memories from the last 24 hours (or since last consolidation)."""
        if not self.memory._conn:
            return []

        cutoff = time.time() - (24 * 3600)
        rows = self.memory._conn.execute(
            """
            SELECT * FROM memories
            WHERE memory_type = 'episodic'
              AND is_archived = 0
              AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (cutoff,),
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

    def _generate_candidate_pairs(
        self,
        episodes: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Generate candidate pairs that may contain contradictions.

        Strategy:
        1. Compute Jaccard similarity between all pairs
        2. Filter to pairs with similarity > threshold
        3. Filter further to pairs containing contradiction signals (negations or antonyms)
        """
        candidates = []

        for i, ep_a in enumerate(episodes):
            for ep_b in episodes[i + 1:]:
                sim = self._jaccard_similarity(ep_a["content"], ep_b["content"])
                if sim < self._similarity_threshold:
                    continue

                if self._has_contradiction_signals(ep_a["content"], ep_b["content"]):
                    candidates.append((ep_a, ep_b))

        return candidates

    def _jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """Compute Jaccard similarity between two texts using word tokens."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _has_contradiction_signals(self, text_a: str, text_b: str) -> bool:
        """Check if two texts contain signals of a contradiction.

        Looks for:
        - Negation words in both texts
        - Antonyms appearing across the two texts
        """
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        # Negation signal: one text has negation, the other doesn't
        neg_a = bool(words_a & _NEGATION_WORDS)
        neg_b = bool(words_b & _NEGATION_WORDS)
        if neg_a != neg_b:
            return True

        # Antonym signal: an antonym pair appears across the two texts
        all_words_a = words_a & set(_ANTONYMS.keys())
        for word in all_words_a:
            antonym = _ANTONYMS[word]
            if antonym in words_b:
                return True

        return False

    async def _check_pair(
        self,
        memory_a: dict[str, Any],
        memory_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Call LLM to determine if two memories contradict each other."""
        prompt = f"""You are analyzing two episodic memories for contradictions. Determine if they contain conflicting information.

Memory A: {memory_a['content']}
Memory B: {memory_b['content']}

If they contradict, respond with JSON: {{"contradicts": true, "resolution": "a_supersedes"|"b_supersedes"|"both_valid"|"ambiguous", "notes": "explanation"}}
If they don't contradict, respond with JSON: {{"contradicts": false, "resolution": null, "notes": "explanation"}}
"""

        request = InferenceRequest(
            model_label="consolidation-semantic",
            prompt=prompt,
            system_prompt="You are a logical contradiction detection system. Be precise and explain your reasoning.",
            timeout_seconds=self._llm_timeout,
        )

        try:
            response = await self.gateway.infer(request)
        except Exception as exc:
            logger.warning("LLM contradiction check failed: %s", exc)
            return {"contradicts": False, "resolution": None, "notes": str(exc)}

        if response.error:
            logger.warning("LLM error in contradiction check: %s", response.error)
            return {"contradicts": False, "resolution": None, "notes": response.error}

        cleaned = _strip_markdown_fences(response.text)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM contradiction response: %s", response.text[:200])
            return {"contradicts": False, "resolution": None, "notes": "parse error"}

        return result

    def _record_resolution(
        self,
        memory_a: dict[str, Any],
        memory_b: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Record a contradiction and apply confidence adjustments."""
        resolution = result.get("resolution", "ambiguous")
        notes = result.get("notes", "")

        now = time.time()

        # Determine which memory to supersede
        superseded_id: str | None = None
        if resolution == "a_supersedes":
            superseded_id = memory_b["id"]
            self._lower_confidence(memory_b["id"])
        elif resolution == "b_supersedes":
            superseded_id = memory_a["id"]
            self._lower_confidence(memory_a["id"])
        elif resolution == "both_valid":
            # Neither is superseded, but we record it for awareness
            pass

        # Write to contradictions table
        if self.memory._conn:
            self.memory._conn.execute(
                """
                INSERT INTO contradictions (id, memory_a_id, memory_b_id, detected_at, resolved_at, resolution, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    memory_a["id"],
                    memory_b["id"],
                    now,
                    now,
                    resolution,
                    notes,
                ),
            )

        return {
            "memory_a_id": memory_a["id"],
            "memory_b_id": memory_b["id"],
            "resolution": resolution,
            "superseded_id": superseded_id,
            "notes": notes,
        }

    def _lower_confidence(self, memory_id: str) -> None:
        """Lower the confidence of a superseded memory by multiplying by 0.7."""
        if not self.memory._conn:
            return
        self.memory._conn.execute(
            """
            UPDATE memories
            SET confidence = MAX(0.0, confidence * 0.7)
            WHERE id = ?
            """,
            (memory_id,),
        )