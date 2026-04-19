"""Unit tests for IdentityDriftDetector."""

from __future__ import annotations

import json
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestIdentityDriftDetector:
    """Tests for IdentityDriftDetector (Job 5 of sleep consolidation)."""

    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory SQLite DB with identity_snapshots table."""
        conn = sqlite3.connect(":memory:", isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE identity_snapshots (
                id TEXT PRIMARY KEY,
                snapshot_data TEXT NOT NULL,
                personality_traits TEXT NOT NULL DEFAULT '{}',
                maturity_stage TEXT NOT NULL,
                self_understanding TEXT NOT NULL DEFAULT '{}',
                snapshot_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_identity_snap_at ON identity_snapshots(snapshot_at);
        """)
        yield conn
        conn.close()

    @pytest.fixture
    def mock_memory(self, in_memory_db):
        """Mock memory architecture with in-memory SQLite."""
        mem = MagicMock()
        mem._conn = in_memory_db
        return mem

    @pytest.fixture
    def mock_persona(self):
        """Mock PersonaManager with developmental identity."""
        persona = MagicMock()
        persona._developmental = {
            "maturity_stage": "developing",
            "personality_traits": {
                "curiosity": {"strength": 0.7, "evidence": ["daydream_001"]},
                "caution": {"strength": 0.4, "evidence": []},
            },
            "self_understanding": {
                "capabilities_recognized": ["reasoning", "planning"],
                "limitations_recognized": ["slow_processing"],
                "tendencies_observed": ["prefers_depth"],
            },
            "drift_log": [],
        }
        persona._save_developmental = MagicMock()
        return persona

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus with async publish."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        yield bus
        bus.reset_mock()

    @pytest.fixture
    def detector(self, mock_persona, mock_memory, mock_event_bus):
        """IdentityDriftDetector with default config."""
        from sentient.sleep.identity_drift_detector import IdentityDriftDetector
        return IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={},
        )

    # -------------------------------------------------------------------------
    # Test 1: Initialization with config
    # -------------------------------------------------------------------------

    def test_init_with_config(self, mock_persona, mock_memory, mock_event_bus):
        """Detector initializes with custom config values."""
        from sentient.sleep.identity_drift_detector import (
            IdentityDriftDetector,
            DEFAULT_ENABLED,
            DEFAULT_DRIFT_THRESHOLD,
            DEFAULT_DRIFT_WINDOW_DAYS,
        )
        config = {
            "enabled": False,
            "drift_threshold": 0.5,
            "drift_window_days": 14,
        }
        d = IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config=config,
        )
        assert d._enabled is False
        assert d._drift_threshold == 0.5
        assert d._drift_window_days == 14

    # -------------------------------------------------------------------------
    # Test 2: Disabled detector returns skipped status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(
        self, mock_persona, mock_memory, mock_event_bus
    ):
        """When enabled=False, detect_drift() returns skipped status."""
        from sentient.sleep.identity_drift_detector import IdentityDriftDetector
        d = IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={"enabled": False},
        )
        result = await d.detect_drift()
        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    # -------------------------------------------------------------------------
    # Test 3: Snapshot creation in identity_snapshots table
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_snapshot_creation(
        self, detector, mock_memory, in_memory_db
    ):
        """detect_drift() creates a snapshot row in identity_snapshots table."""
        result = await detector.detect_drift()

        rows = in_memory_db.execute("SELECT * FROM identity_snapshots").fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row["maturity_stage"] == "developing"
        assert row["personality_traits"] is not None
        assert row["snapshot_at"] > 0

    # -------------------------------------------------------------------------
    # Test 4: Trait drift detection (> drift_threshold)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_trait_drift_detection(
        self, mock_persona, mock_memory, mock_event_bus, in_memory_db
    ):
        """When a trait's strength changes by > drift_threshold, it is flagged."""
        from sentient.sleep.identity_drift_detector import IdentityDriftDetector

        # Create an old snapshot with different trait strength
        old_traits = {"curiosity": {"strength": 0.4}}  # current is 0.7, diff=0.3
        old_su = {"capabilities_recognized": [], "limitations_recognized": [], "tendencies_observed": []}
        in_memory_db.execute(
            """INSERT INTO identity_snapshots
               (id, snapshot_data, personality_traits, maturity_stage,
                self_understanding, snapshot_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "old-snapshot-001",
                json.dumps({}),
                json.dumps(old_traits),
                "developing",
                json.dumps(old_su),
                time.time() - (8 * 86400),  # 8 days ago (>7 day window)
            ),
        )

        d = IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={"drift_threshold": 0.3},
        )

        result = await d.detect_drift()

        assert result["drifts_detected"] >= 1
        drift_types = [d["type"] for d in result["drifts"]]
        assert "trait_drift" in drift_types

    # -------------------------------------------------------------------------
    # Test 5: Self-understanding change detection
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_self_understanding_change_detection(
        self, mock_persona, mock_memory, mock_event_bus, in_memory_db
    ):
        """When self_understanding category has items added or removed, it is flagged."""
        from sentient.sleep.identity_drift_detector import IdentityDriftDetector

        # Create an old snapshot with different self_understanding
        old_traits = {}
        old_su = {
            "capabilities_recognized": [],  # currently has 2 items
            "limitations_recognized": ["slow_processing"],  # matches, so no change
            "tendencies_observed": ["prefers_depth"],  # matches, so no change
        }
        in_memory_db.execute(
            """INSERT INTO identity_snapshots
               (id, snapshot_data, personality_traits, maturity_stage,
                self_understanding, snapshot_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "old-snapshot-002",
                json.dumps({}),
                json.dumps(old_traits),
                "developing",
                json.dumps(old_su),
                time.time() - (8 * 86400),
            ),
        )

        d = IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={"drift_threshold": 0.3},
        )

        result = await d.detect_drift()

        # capabilities_recognized changed: [] -> ["reasoning", "planning"]
        su_drift = [dr for dr in result["drifts"] if dr.get("type") == "self_understanding_change"]
        assert len(su_drift) >= 1
        assert su_drift[0]["category"] == "capabilities_recognized"

    # -------------------------------------------------------------------------
    # Test 6: Drift log entries added
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_drift_log_entries_added(
        self, mock_persona, mock_memory, mock_event_bus, in_memory_db
    ):
        """Drift entries are appended to the developmental identity's drift_log."""
        from sentient.sleep.identity_drift_detector import IdentityDriftDetector

        # Create an old snapshot with significantly different traits
        old_traits = {"curiosity": {"strength": 0.2}}  # diff from current 0.7 = 0.5
        old_su = {"capabilities_recognized": [], "limitations_recognized": [], "tendencies_observed": []}
        in_memory_db.execute(
            """INSERT INTO identity_snapshots
               (id, snapshot_data, personality_traits, maturity_stage,
                self_understanding, snapshot_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "old-snapshot-003",
                json.dumps({}),
                json.dumps(old_traits),
                "developing",
                json.dumps(old_su),
                time.time() - (8 * 86400),
            ),
        )

        mock_persona._developmental["drift_log"] = []
        d = IdentityDriftDetector(
            persona=mock_persona,
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={"drift_threshold": 0.3},
        )

        await d.detect_drift()

        # Verify drift_log was updated
        assert len(mock_persona._developmental["drift_log"]) >= 1
        # Verify _save_developmental was called
        mock_persona._save_developmental.assert_called()