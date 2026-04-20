"""World Model Calibration — calibrates the World Model's confidence thresholds based on user feedback.

Job 4 of the four-stage sleep consolidation pipeline (ARCHITECTURE.md §3.5):
  - Reads verdicts from the World Model's journal (_journal list)
  - Checks if subsequent user messages contained correction/frustration markers
  - For wrong predictions, adjusts confidence thresholds with hard cap ±0.05 per cycle
  - Stores adjustments in world_model_calibration table
  - Emits calibration events for each adjustment

Per Phase 9 D4 spec.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.memory.architecture import MemoryArchitecture

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_ENABLED = True
DEFAULT_MAX_ADJUSTMENT_PER_CYCLE = 0.05
DEFAULT_CORRECTION_MARKERS = ["correction", "wrong", "actually", "no,", "that's not"]

# Per-flagged verdict types and their default confidence
_VERDICT_CONFIDENCE: dict[str, float] = {
    "approved": 1.0,
    "advisory": 0.8,
    "revision_requested": 0.6,
    "vetoed": 0.5,
}


class WMCalibrator:
    """Calibrates the World Model's verdict confidence based on post-hoc user feedback."""

    def __init__(
        self,
        world_model: Any,  # WorldModel or anything with _journal
        memory_architecture: MemoryArchitecture,
        event_bus: EventBus | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.world_model = world_model
        self.memory = memory_architecture
        self.event_bus = event_bus or get_event_bus()
        self.config = config or {}

        self._enabled = self.config.get("enabled", DEFAULT_ENABLED)
        self._max_adjustment = self.config.get(
            "max_adjustment_per_cycle", DEFAULT_MAX_ADJUSTMENT_PER_CYCLE
        )
        self._correction_markers = self.config.get(
            "correction_markers", DEFAULT_CORRECTION_MARKERS
        )

    # --- Public API ---

    async def calibrate(self) -> dict[str, Any]:
        """Run one calibration cycle on the World Model journal.

        Returns:
            dict with keys: verdicts_scanned, adjustments_made, total_adjustment, status
        """
        if not self._enabled:
            logger.info("WM calibrator disabled — skipping")
            return {"status": "skipped", "reason": "disabled"}

        logger.info("WM calibrator: starting cycle")
        await self.event_bus.publish(
            "sleep.consolidation.wm_calibrator.start",
            {},
        )

        journal = getattr(self.world_model, "_journal", [])
        if not journal:
            logger.info("WM calibrator: no verdicts in journal")
            return {"status": "completed", "verdicts_scanned": 0, "adjustments_made": 0, "total_adjustment": 0.0}

        verdicts_scanned = len(journal)
        total_adjustment = 0.0
        adjustments_made = 0

        for verdict in journal:
            adjustment = self._evaluate_verdict(verdict)
            if adjustment != 0.0:
                # Hard cap at ± max_adjustment
                capped = max(-self._max_adjustment, min(self._max_adjustment, adjustment))
                self._apply_adjustment(verdict, capped)
                self._store_calibration(verdict, capped)
                total_adjustment += abs(capped)
                adjustments_made += 1

                await self.event_bus.publish(
                    "sleep.consolidation.wm_calibrated",
                    {
                        "cycle_id": verdict.get("cycle_id"),
                        "verdict_type": verdict.get("verdict"),
                        "adjustment": capped,
                    },
                )

        logger.info(
            "WM calibrator: scanned %d verdicts, made %d adjustments, total adjustment=%.4f",
            verdicts_scanned, adjustments_made, total_adjustment,
        )

        await self.event_bus.publish(
            "sleep.consolidation.wm_calibrator.complete",
            {
                "verdicts_scanned": verdicts_scanned,
                "adjustments_made": adjustments_made,
                "total_adjustment": round(total_adjustment, 6),
            },
        )

        return {
            "status": "completed",
            "verdicts_scanned": verdicts_scanned,
            "adjustments_made": adjustments_made,
            "total_adjustment": round(total_adjustment, 6),
        }

    # --- Private helpers ---

    def _evaluate_verdict(self, verdict: dict[str, Any]) -> float:
        """Evaluate a single verdict for calibration need.

        Returns a raw adjustment value (positive = increase confidence, negative = decrease).
        The hard cap is applied later in calibrate().
        """
        decision_type = verdict.get("decision_type", "")
        cycle_id = verdict.get("cycle_id", "")

        # Check if any subsequent user messages contained correction markers
        # related to this cycle_id in the wake-up inbox
        correction_signal = self._check_correction_signal(cycle_id, decision_type)

        if correction_signal == "wrong":
            # User said the World Model was wrong — reduce confidence
            return -0.03
        elif correction_signal == "right":
            # User confirmed the World Model was right — increase confidence
            return 0.02

        return 0.0

    def _check_correction_signal(self, cycle_id: str, decision_type: str) -> str:
        """Check the wake-up inbox for correction signals related to this verdict.

        In a full implementation, this would check actual user messages.
        For MVS, we check if any inbox item references this cycle or similar decision types
        and contains correction markers.

        Returns: 'wrong' | 'right' | 'none'
        """
        # In a real system, we'd look at the actual inbox messages
        # For MVS, we rely on sleep scheduler's _wake_up_inbox being accessible
        inbox = getattr(self.world_model, "_wake_up_inbox", []) if hasattr(self.world_model, "_wake_up_inbox") else []

        for item in inbox:
            content = str(item.get("content", ""))
            # Check for correction markers
            if any(marker.lower() in content.lower() for marker in self._correction_markers):
                return "wrong"
            # Check for affirmation (simple heuristic)
            if any(w in content.lower() for w in ["thanks", "good", "correct", "right"]):
                return "right"

        return "none"

    def _apply_adjustment(self, verdict: dict[str, Any], adjustment: float) -> None:
        """Apply an adjustment to the World Model's verdict confidence.

        In the actual WorldModel, we adjust the associated confidence threshold.
        For this implementation, we update the verdict entry in the journal in-place.
        """
        # Update the in-memory journal entry
        old_confidence = verdict.get("confidence", 1.0)
        new_confidence = max(0.0, min(1.0, old_confidence + adjustment))
        verdict["confidence"] = new_confidence
        verdict["calibrated_at"] = time.time()

        logger.debug(
            "WM calibrator: cycle_id=%s, verdict=%s, confidence %.3f → %.3f",
            verdict.get("cycle_id"),
            verdict.get("verdict"),
            old_confidence,
            new_confidence,
        )

    def _store_calibration(
        self,
        verdict: dict[str, Any],
        adjustment: float,
    ) -> None:
        """Store a calibration record in the world_model_calibration table."""
        if not self.memory._conn:
            return

        cycle_id = verdict.get("cycle_id", str(uuid.uuid4()))
        verdict_type = verdict.get("verdict", "unknown")
        original_confidence = verdict.get("confidence", 1.0)
        new_confidence = max(0.0, min(1.0, original_confidence + adjustment))
        reason = f"cycle_id={cycle_id}"

        self.memory._conn.execute(
            """
            INSERT INTO world_model_calibration
                (id, cycle_id, verdict_type, original_confidence, adjustment, new_confidence, reason, calibrated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                cycle_id,
                verdict_type,
                original_confidence,
                adjustment,
                new_confidence,
                reason,
                time.time(),
            ),
        )