"""Memory Gatekeeper — logic-based write-path filtering.

Per DD-008, the write path uses ZERO LLM inference. Pure deterministic
logic for:
  - Importance threshold (adaptive)
  - Exact deduplication (content hash)
  - Semantic deduplication (embedding similarity)
  - Contradiction detection
  - Recency weighting (today's memories auto-pass)

This keeps the write path fast and predictable.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GatekeeperDecision:
    """Outcome of the gatekeeper's evaluation of a memory candidate."""

    action: str   # "store" | "reinforce" | "update" | "flag_contradiction" | "skip"
    reason: str
    target_memory_id: str | None = None   # For reinforce/update
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryGatekeeper:
    """Filters memory candidates before storage. No LLM involvement."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.importance_threshold = config.get("importance_threshold", 0.3)
        self.semantic_dedup_similarity = config.get("semantic_dedup_similarity", 0.92)
        self.recency_auto_pass_hours = config.get("recency_auto_pass_hours", 24)

    def evaluate(
        self,
        candidate: dict[str, Any],
        existing_by_hash: dict[str, dict] | None = None,
        similar_memories: list[dict] | None = None,
    ) -> GatekeeperDecision:
        """Evaluate a memory candidate and return a decision.

        Args:
            candidate: The memory candidate from Cognitive Core reflection.
              Expected keys: content, type, tags, importance, created_at
            existing_by_hash: Dict of content hash → memory (for exact dedup).
            similar_memories: List of semantically-similar existing memories
              (for semantic dedup and contradiction detection).
        """
        content = candidate.get("content", "")
        importance = float(candidate.get("importance", 0.5))
        created_at = candidate.get("created_at", time.time())

        # Step 1: Recency auto-pass — very recent memories skip threshold
        age_hours = (time.time() - created_at) / 3600
        if age_hours < self.recency_auto_pass_hours:
            # Still check for dedup, but skip importance threshold
            pass
        else:
            # Step 2: Importance threshold
            if importance < self.importance_threshold:
                return GatekeeperDecision(
                    action="skip",
                    reason=f"importance {importance:.2f} below threshold {self.importance_threshold}",
                )

        # Step 3: Exact dedup via content hash
        content_hash = self._hash_content(content)
        if existing_by_hash and content_hash in existing_by_hash:
            existing = existing_by_hash[content_hash]
            return GatekeeperDecision(
                action="reinforce",
                reason="exact content match — reinforcing existing memory",
                target_memory_id=existing.get("id"),
            )

        # Step 4: Semantic dedup via embedding similarity
        if similar_memories:
            for similar in similar_memories:
                similarity = similar.get("similarity", 0.0)
                if similarity >= self.semantic_dedup_similarity:
                    return GatekeeperDecision(
                        action="update",
                        reason=f"semantic match ({similarity:.2f}) — updating existing",
                        target_memory_id=similar.get("id"),
                    )

        # Step 5: Contradiction detection
        # If candidate content directly contradicts an existing memory with
        # high semantic similarity but differing key facts, flag it.
        for similar in similar_memories or []:
            if 0.6 <= similar.get("similarity", 0) < self.semantic_dedup_similarity:
                # Could be a contradiction — flag for sleep-time resolution
                if self._possible_contradiction(candidate, similar):
                    return GatekeeperDecision(
                        action="flag_contradiction",
                        reason="possible contradiction with existing memory",
                        target_memory_id=similar.get("id"),
                        metadata={"contradicts": similar.get("id")},
                    )

        # Passes all filters — store it
        return GatekeeperDecision(
            action="store",
            reason="passes all gatekeeper filters",
            metadata={"content_hash": content_hash},
        )

    @staticmethod
    def _hash_content(content: str) -> str:
        """SHA-256 hash for exact dedup."""
        return hashlib.sha256(content.strip().lower().encode()).hexdigest()

    @staticmethod
    def _possible_contradiction(candidate: dict, existing: dict) -> bool:
        """Very simple contradiction heuristic.

        MVS: detects negation differences (one has "not", the other doesn't).
        Phase 2+ can use more sophisticated detection during sleep.
        """
        c_content = candidate.get("content", "").lower()
        e_content = existing.get("processed_content", "").lower()
        negations = ["not", "never", "no ", "n't"]
        c_has_neg = any(n in c_content for n in negations)
        e_has_neg = any(n in e_content for n in negations)
        return c_has_neg != e_has_neg
