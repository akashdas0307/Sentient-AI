"""Unit tests for WMCalibrator."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestWMCalibrator:
    """Tests for WMCalibrator (Job 4 of sleep consolidation)."""

    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory SQLite DB with full schema."""
        conn = sqlite3.connect(":memory:", isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at REAL NOT NULL,
                last_accessed_at REAL,
                access_count INTEGER DEFAULT 0,
                reinforcement_count INTEGER DEFAULT 1,
                source_envelope_id TEXT,
                source_cycle_id TEXT,
                entity_tags TEXT DEFAULT '[]',
                topic_tags TEXT DEFAULT '[]',
                emotional_tags TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                is_archived INTEGER DEFAULT 0,
                archived_at REAL
            );
            CREATE TABLE world_model_calibration (
                id TEXT PRIMARY KEY,
                cycle_id TEXT NOT NULL,
                verdict_type TEXT NOT NULL,
                original_confidence REAL NOT NULL,
                adjustment REAL NOT NULL,
                new_confidence REAL NOT NULL,
                reason TEXT,
                calibrated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wm_cal_cycle ON world_model_calibration(cycle_id);
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
    def mock_world_model(self):
        """Mock WorldModel with a populated journal."""
        wm = MagicMock()
        wm._journal = [
            {
                "cycle_id": "cycle-001",
                "decision_type": "action_proposal",
                "verdict": "approved",
                "confidence": 0.9,
                "timestamp": time.time() - 3600,
            },
            {
                "cycle_id": "cycle-002",
                "decision_type": "question_response",
                "verdict": "revision_requested",
                "confidence": 0.6,
                "timestamp": time.time() - 1800,
            },
        ]
        wm._wake_up_inbox = []
        return wm

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus with async publish."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        yield bus
        bus.reset_mock()

    @pytest.fixture
    def calibrator(self, mock_world_model, mock_memory, mock_event_bus):
        """WMCalibrator with default config.

        The calibrator's mock_memory._conn is set to in_memory_db from
        the calibrator's own fixture chain (mock_memory -> in_memory_db).
        Tests access the same DB via mock_memory._conn.
        """
        from sentient.sleep.wm_calibrator import WMCalibrator
        return WMCalibrator(
            world_model=mock_world_model,
            memory_architecture=mock_memory,
            event_bus=mock_event_bus,
            config={},
        )

    # -------------------------------------------------------------------------
    # Test 1: Initialization with config
    # -------------------------------------------------------------------------

    def test_init_with_config(self, mock_world_model, mock_memory, mock_event_bus):
        """Calibrator initializes with custom config values."""
        from sentient.sleep.wm_calibrator import (
            WMCalibrator,
        )
        config = {
            "enabled": False,
            "max_adjustment_per_cycle": 0.03,
            "correction_markers": ["incorrect", "mistake"],
        }
        c = WMCalibrator(
            world_model=mock_world_model,
            memory_architecture=mock_memory,
            event_bus=mock_event_bus,
            config=config,
        )
        assert c._enabled is False
        assert c._max_adjustment == 0.03
        assert c._correction_markers == ["incorrect", "mistake"]

    # -------------------------------------------------------------------------
    # Test 2: Disabled calibrator returns skipped status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(
        self, mock_world_model, mock_memory, mock_event_bus
    ):
        """When enabled=False, calibrate() returns skipped status."""
        from sentient.sleep.wm_calibrator import WMCalibrator
        c = WMCalibrator(
            world_model=mock_world_model,
            memory_architecture=mock_memory,
            event_bus=mock_event_bus,
            config={"enabled": False},
        )
        result = await c.calibrate()
        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    # -------------------------------------------------------------------------
    # Test 3: Correction marker detection
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_correction_marker_detected(self, mock_memory, mock_event_bus):
        """When inbox contains correction markers, wrong verdict is flagged."""
        from sentient.sleep.wm_calibrator import WMCalibrator
        wm = MagicMock()
        wm._journal = [
            {
                "cycle_id": "cycle-100",
                "decision_type": "action_proposal",
                "verdict": "approved",
                "confidence": 1.0,
                "timestamp": time.time() - 300,
            },
        ]
        wm._wake_up_inbox = [
            {"content": "No, that's not right — I actually wanted something different."},
        ]
        c = WMCalibrator(
            world_model=wm,
            memory_architecture=mock_memory,
            event_bus=mock_event_bus,
            config={},
        )
        result = await c.calibrate()
        assert result["adjustments_made"] >= 1

    # -------------------------------------------------------------------------
    # Test 4: Hard cap on adjustment (±0.05)
    # -------------------------------------------------------------------------

    def test_hard_cap_on_adjustment(self, calibrator):
        """Raw adjustments are capped at ±max_adjustment (0.05 by default)."""
        # A verdict with correction markers should get -0.03 raw
        # With a mock inbox containing markers
        calibrator.world_model._wake_up_inbox = [
            {"content": "That was wrong — you made a mistake."},
        ]

        raw = calibrator._evaluate_verdict(
            {
                "cycle_id": "cycle-cap",
                "decision_type": "test",
                "verdict": "approved",
                "confidence": 1.0,
                "timestamp": time.time(),
            }
        )
        assert abs(raw) <= calibrator._max_adjustment

    # -------------------------------------------------------------------------
    # Test 5: Calibration table writes
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_calibration_table_writes(
        self, calibrator, mock_world_model, mock_memory
    ):
        """When adjustments are made, rows are written to world_model_calibration table."""
        calibrator.world_model._wake_up_inbox = [
            {"content": "Actually that was wrong."},
        ]
        calibrator.world_model._journal = [
            {
                "cycle_id": "cycle-tab",
                "decision_type": "action",
                "verdict": "approved",
                "confidence": 1.0,
                "timestamp": time.time() - 300,
            },
        ]

        await calibrator.calibrate()

        rows = mock_memory._conn.execute("SELECT * FROM world_model_calibration").fetchall()
        assert len(rows) >= 1
        row = rows[0]
        assert row["cycle_id"] == "cycle-tab"
        assert row["verdict_type"] == "approved"

    # -------------------------------------------------------------------------
    # Test 6: Event emission
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_event_emission(self, calibrator, mock_event_bus):
        """Events are published for start, wm_calibrated, and complete."""
        calibrator.world_model._wake_up_inbox = [
            {"content": "No, that's incorrect."},
        ]
        calibrator.world_model._journal = [
            {
                "cycle_id": "cycle-ev",
                "decision_type": "action",
                "verdict": "revision_requested",
                "confidence": 0.7,
                "timestamp": time.time() - 300,
            },
        ]

        await calibrator.calibrate()

        published_events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
        assert "sleep.consolidation.wm_calibrator.start" in published_events
        assert "sleep.consolidation.wm_calibrated" in published_events
        assert "sleep.consolidation.wm_calibrator.complete" in published_events
