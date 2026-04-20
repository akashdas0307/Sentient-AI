"""Procedural Refiner — reinforces, decays, and archives procedural memory patterns.

Job 3 of the four-stage sleep consolidation pipeline (ARCHITECTURE.md §3.5):
  - Reinforce: patterns with high reinforcement_count get confidence bump
  - Decay: patterns unreinforced for N days get confidence decrement
  - Archive: patterns below threshold are deleted from procedural_memory
  - Emits consolidated event

Per Phase 9 D5 spec.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.memory.architecture import MemoryArchitecture

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_ENABLED = True
DEFAULT_REINFORCEMENT_THRESHOLD = 5
DEFAULT_STALE_DAYS = 30
DEFAULT_ARCHIVE_THRESHOLD = 0.1
DEFAULT_CONFIDENCE_BUMP = 0.02
DEFAULT_CONFIDENCE_DECAY = 0.01


class ProceduralRefiner:
    """Refines procedural memory patterns during sleep consolidation."""

    def __init__(
        self,
        memory: MemoryArchitecture,
        event_bus: EventBus | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.memory = memory
        self.event_bus = event_bus or get_event_bus()
        self.config = config or {}

        self._enabled = self.config.get("enabled", DEFAULT_ENABLED)
        self._reinforcement_threshold = self.config.get(
            "reinforcement_threshold", DEFAULT_REINFORCEMENT_THRESHOLD
        )
        self._stale_days = self.config.get("stale_days", DEFAULT_STALE_DAYS)
        self._archive_threshold = self.config.get("archive_threshold", DEFAULT_ARCHIVE_THRESHOLD)
        self._confidence_bump = self.config.get("confidence_bump", DEFAULT_CONFIDENCE_BUMP)
        self._confidence_decay = self.config.get("confidence_decay", DEFAULT_CONFIDENCE_DECAY)

    # --- Public API ---

    async def refine(self) -> dict[str, Any]:
        """Run one refinement cycle on procedural patterns.

        Returns:
            dict with keys: reinforced, decayed, archived, total_processed, status
        """
        if not self._enabled:
            logger.info("Procedural refiner disabled — skipping")
            return {"status": "skipped", "reason": "disabled"}

        logger.info("Procedural refiner: starting cycle")
        await self.event_bus.publish(
            "sleep.consolidation.procedural_refiner.start",
            {},
        )

        # Fetch all patterns
        patterns = await self.memory.procedural_store.list_all()
        total_processed = len(patterns)

        # Decay stale patterns first (before reinforce updates last_reinforced)
        decayed = await self._decay_stale()

        # Reinforce high-reinforcement patterns (exclude stale ones already processed)
        reinforced = await self._reinforce_high_count()

        # Archive low-confidence patterns
        archived = await self._archive_low_confidence()

        logger.info(
            "Procedural refiner: processed %d patterns — reinforced=%d, decayed=%d, archived=%d",
            total_processed, reinforced, decayed, archived,
        )

        await self.event_bus.publish(
            "sleep.consolidation.procedural_refined",
            {
                "reinforced": reinforced,
                "decayed": decayed,
                "archived": archived,
                "total_processed": total_processed,
            },
        )

        return {
            "status": "completed",
            "reinforced": reinforced,
            "decayed": decayed,
            "archived": archived,
            "total_processed": total_processed,
        }

    # --- Private helpers ---

    async def _reinforce_high_count(self) -> int:
        """Bump confidence for patterns with reinforcement_count >= threshold.

        Excludes patterns that are stale (last_reinforced < stale_cutoff) to avoid
        reinforcing patterns that were just decayed.

        Returns the count of reinforced patterns.
        """
        if not self.memory._conn:
            return 0

        stale_cutoff = time.time() - (self._stale_days * 86400)

        self.memory._conn.execute(
            """
            UPDATE procedural_memory
            SET confidence = MIN(1.0, confidence + ?)
            WHERE reinforcement_count >= ?
              AND last_reinforced >= ?
            """,
            (self._confidence_bump, self._reinforcement_threshold, stale_cutoff),
        )

        row = self.memory._conn.execute(
            "SELECT COUNT(*) as c FROM procedural_memory WHERE reinforcement_count >= ? AND last_reinforced >= ?",
            (self._reinforcement_threshold, stale_cutoff),
        ).fetchone()
        return row["c"] if row else 0

    async def _decay_stale(self) -> int:
        """Decrement confidence for patterns not reinforced in N days.

        Returns the count of decayed patterns.
        """
        if not self.memory._conn:
            return 0

        stale_cutoff = time.time() - (self._stale_days * 86400)

        # Count before update for reporting
        row = self.memory._conn.execute(
            "SELECT COUNT(*) as c FROM procedural_memory WHERE last_reinforced < ?",
            (stale_cutoff,),
        ).fetchone()
        decayed = row["c"] if row else 0

        self.memory._conn.execute(
            """
            UPDATE procedural_memory
            SET confidence = MAX(0.0, confidence - ?)
            WHERE last_reinforced < ?
            """,
            (self._confidence_decay, stale_cutoff),
        )

        return decayed

    async def _archive_low_confidence(self) -> int:
        """Delete patterns with confidence below archive threshold.

        Returns the count of archived (deleted) patterns.
        """
        if not self.memory._conn:
            return 0

        # Count before delete for reporting
        row = self.memory._conn.execute(
            "SELECT COUNT(*) as c FROM procedural_memory WHERE confidence < ?",
            (self._archive_threshold,),
        ).fetchone()
        archived = row["c"] if row else 0

        self.memory._conn.execute(
            "DELETE FROM procedural_memory WHERE confidence < ?",
            (self._archive_threshold,),
        )

        return archived
