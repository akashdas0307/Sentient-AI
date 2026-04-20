"""Identity Drift Detector — detects personality trait drift over time.

Job 5 of the four-stage sleep consolidation pipeline (ARCHITECTURE.md §3.5):
  - Snapshots current developmental identity into identity_snapshots table
  - Compares with snapshots from N days ago
  - Flags traits with strength change > drift_threshold
  - Flags self_understanding category changes
  - Logs drifts to developmental identity's drift_log
  - OBSERVATIONAL ONLY: logs but does not self-correct

Per Phase 9 D5 spec.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.memory.architecture import MemoryArchitecture
from sentient.persona.identity_manager import PersonaManager

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_ENABLED = True
DEFAULT_DRIFT_THRESHOLD = 0.3
DEFAULT_DRIFT_WINDOW_DAYS = 7


class IdentityDriftDetector:
    """Detects personality drift during sleep consolidation."""

    def __init__(
        self,
        persona: PersonaManager,
        memory: MemoryArchitecture,
        event_bus: EventBus | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.persona = persona
        self.memory = memory
        self.event_bus = event_bus or get_event_bus()
        self.config = config or {}

        self._enabled = self.config.get("enabled", DEFAULT_ENABLED)
        self._drift_threshold = self.config.get("drift_threshold", DEFAULT_DRIFT_THRESHOLD)
        self._drift_window_days = self.config.get("drift_window_days", DEFAULT_DRIFT_WINDOW_DAYS)

    # --- Public API ---

    async def detect_drift(self) -> dict[str, Any]:
        """Run one drift detection cycle.

        Returns:
            dict with keys: snapshot_taken, drifts_detected, drifts, status
        """
        if not self._enabled:
            logger.info("Identity drift detector disabled — skipping")
            return {"status": "skipped", "reason": "disabled"}

        logger.info("Identity drift detector: starting cycle")
        await self.event_bus.publish(
            "sleep.consolidation.identity_drift_detector.start",
            {},
        )

        # Take snapshot of current developmental identity
        snapshot_id = await self._take_snapshot()

        # Fetch previous snapshot from drift window
        previous = await self._fetch_previous_snapshot()

        # Compare and detect drifts
        drifts = []
        if previous:
            drifts = await self._detect_drift(previous)

        # Log drifts to developmental identity
        await self._log_drifts(drifts)

        logger.info(
            "Identity drift detector: snapshot=%s, drifts detected=%d",
            snapshot_id, len(drifts),
        )

        await self.event_bus.publish(
            "sleep.consolidation.identity_drift_detected",
            {
                "snapshot_taken": snapshot_id is not None,
                "drifts_detected": len(drifts),
                "drifts": drifts,
            },
        )

        return {
            "status": "completed",
            "snapshot_taken": snapshot_id is not None,
            "drifts_detected": len(drifts),
            "drifts": drifts,
        }

    # --- Private helpers ---

    async def _take_snapshot(self) -> str | None:
        """Snapshot current developmental identity into identity_snapshots table.

        Returns the snapshot_id or None if failed.
        """
        if not self.memory._conn:
            return None

        snapshot_id = str(uuid.uuid4())
        developmental = self.persona._developmental

        personality_traits = json.dumps(developmental.get("personality_traits", {}))
        self_understanding = json.dumps(developmental.get("self_understanding", {}))
        maturity_stage = developmental.get("maturity_stage", "nascent")
        snapshot_data = json.dumps(developmental)

        self.memory._conn.execute(
            """
            INSERT INTO identity_snapshots
                (id, snapshot_data, personality_traits, maturity_stage, self_understanding, snapshot_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                snapshot_data,
                personality_traits,
                maturity_stage,
                self_understanding,
                time.time(),
            ),
        )

        logger.debug("Identity snapshot taken: %s", snapshot_id)
        return snapshot_id

    async def _fetch_previous_snapshot(self) -> dict[str, Any] | None:
        """Fetch the most recent snapshot older than the drift window.

        Returns the snapshot dict or None if none exists.
        """
        if not self.memory._conn:
            return None

        window_seconds = self._drift_window_days * 86400
        cutoff = time.time() - window_seconds

        row = self.memory._conn.execute(
            """
            SELECT * FROM identity_snapshots
            WHERE snapshot_at < ?
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            (cutoff,),
        ).fetchone()

        if not row:
            return None

        snapshot = dict(row)
        # Parse JSON fields
        snapshot["personality_traits"] = json.loads(snapshot.get("personality_traits", "{}"))
        snapshot["self_understanding"] = json.loads(snapshot.get("self_understanding", "{}"))
        return snapshot

    async def _detect_drift(self, previous: dict[str, Any]) -> list[dict[str, Any]]:
        """Compare current developmental identity with a previous snapshot.

        Returns a list of drift entries.
        """
        drifts = []
        current = self.persona._developmental

        current_traits = current.get("personality_traits", {})
        previous_traits = previous.get("personality_traits", {})

        # Check for trait drift
        all_trait_keys = set(current_traits.keys()) | set(previous_traits.keys())
        for trait_name in all_trait_keys:
            current_strength = current_traits.get(trait_name, {}).get("strength", 0.0)
            previous_strength = previous_traits.get(trait_name, {}).get("strength", 0.0)
            magnitude = abs(current_strength - previous_strength)

            if magnitude > self._drift_threshold:
                drift = {
                    "detected_at": time.time(),
                    "type": "trait_drift",
                    "trait": trait_name,
                    "detail": f"Trait '{trait_name}' drifted from {previous_strength:.2f} to {current_strength:.2f}",
                    "magnitude": round(magnitude, 4),
                    "previous_value": previous_strength,
                    "current_value": current_strength,
                }
                drifts.append(drift)

        # Check for self_understanding changes
        current_su = current.get("self_understanding", {})
        previous_su = previous.get("self_understanding", {})

        for category in ("capabilities_recognized", "limitations_recognized", "tendencies_observed"):
            current_items = set(current_su.get(category, []))
            previous_items = set(previous_su.get(category, []))

            added = current_items - previous_items
            removed = previous_items - current_items

            if added or removed:
                drift = {
                    "detected_at": time.time(),
                    "type": "self_understanding_change",
                    "category": category,
                    "detail": f"Category '{category}': added {list(added)}, removed {list(removed)}",
                    "added": list(added),
                    "removed": list(removed),
                    "magnitude": len(added) + len(removed),
                }
                drifts.append(drift)

        return drifts

    async def _log_drifts(self, drifts: list[dict[str, Any]]) -> None:
        """Append drift entries to the developmental identity's drift_log.

        OBSERVATIONAL ONLY: does not self-correct.
        """
        if not drifts:
            return

        drift_log = self.persona._developmental.setdefault("drift_log", [])
        drift_log.extend(drifts)
        self.persona._developmental["drift_log"] = drift_log

        # Save to disk
        self.persona._save_developmental()

        logger.info("Identity drift detector: logged %d drift entries", len(drifts))
