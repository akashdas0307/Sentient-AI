"""Unit tests for ProceduralRefiner."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestProceduralRefiner:
    """Tests for ProceduralRefiner (Job 3 of sleep consolidation)."""

    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory SQLite DB with procedural_memory table."""
        conn = sqlite3.connect(":memory:", isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE procedural_memory (
                pattern_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                trigger_context TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                evidence_episode_ids TEXT NOT NULL DEFAULT '[]',
                evidence_count INTEGER NOT NULL DEFAULT 0,
                first_observed REAL NOT NULL,
                last_reinforced REAL NOT NULL,
                reinforcement_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_procedural_confidence ON procedural_memory(confidence);
            CREATE INDEX IF NOT EXISTS idx_procedural_first_observed ON procedural_memory(first_observed);
        """)
        yield conn
        conn.close()

    @pytest.fixture
    def mock_memory(self, in_memory_db):
        """Mock memory architecture with in-memory SQLite."""
        mem = MagicMock()
        mem._conn = in_memory_db
        # Mock procedural_store with list_all that returns rows from the connection
        class FakeProceduralStore:
            def __init__(self, conn):
                self._conn = conn

            async def list_all(self):
                rows = self._conn.execute("SELECT * FROM procedural_memory").fetchall()
                return [dict(row) for row in rows]

        mem.procedural_store = FakeProceduralStore(in_memory_db)
        return mem

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus with async publish."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        yield bus
        bus.reset_mock()

    @pytest.fixture
    def refiner(self, mock_memory, mock_event_bus):
        """ProceduralRefiner with default config."""
        from sentient.sleep.procedural_refiner import ProceduralRefiner
        return ProceduralRefiner(
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={},
        )

    # -------------------------------------------------------------------------
    # Test 1: Initialization with config
    # -------------------------------------------------------------------------

    def test_init_with_config(self, mock_memory, mock_event_bus):
        """Refiner initializes with custom config values."""
        from sentient.sleep.procedural_refiner import (
            ProceduralRefiner,
            DEFAULT_ENABLED,
            DEFAULT_REINFORCEMENT_THRESHOLD,
            DEFAULT_STALE_DAYS,
            DEFAULT_ARCHIVE_THRESHOLD,
        )
        config = {
            "enabled": False,
            "reinforcement_threshold": 10,
            "stale_days": 60,
            "archive_threshold": 0.05,
            "confidence_bump": 0.03,
            "confidence_decay": 0.02,
        }
        r = ProceduralRefiner(
            memory=mock_memory,
            event_bus=mock_event_bus,
            config=config,
        )
        assert r._enabled is False
        assert r._reinforcement_threshold == 10
        assert r._stale_days == 60
        assert r._archive_threshold == 0.05
        assert r._confidence_bump == 0.03
        assert r._confidence_decay == 0.02

    # -------------------------------------------------------------------------
    # Test 2: Disabled refiner returns skipped status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(self, mock_memory, mock_event_bus):
        """When enabled=False, refine() returns skipped status."""
        from sentient.sleep.procedural_refiner import ProceduralRefiner
        r = ProceduralRefiner(
            memory=mock_memory,
            event_bus=mock_event_bus,
            config={"enabled": False},
        )
        result = await r.refine()
        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    # -------------------------------------------------------------------------
    # Test 3: Reinforcement of high-reinforcement patterns
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reinforcement_of_high_count(
        self, refiner, mock_memory, in_memory_db
    ):
        """Patterns with reinforcement_count >= threshold get confidence bump."""
        now = time.time()

        # Insert two patterns: one high-reinforcement (>=5), one low
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-high", "High count pattern", "", 0.5,
                "[]", 0, now, now, 7, now,  # reinforcement_count = 7 (>=5)
            ),
        )
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-low", "Low count pattern", "", 0.5,
                "[]", 0, now, now, 2, now,  # reinforcement_count = 2 (<5)
            ),
        )

        result = await refiner.refine()

        # Check confidence after reinforcement
        high_row = in_memory_db.execute(
            "SELECT confidence FROM procedural_memory WHERE pattern_id = ?",
            ("pattern-high",),
        ).fetchone()
        low_row = in_memory_db.execute(
            "SELECT confidence FROM procedural_memory WHERE pattern_id = ?",
            ("pattern-low",),
        ).fetchone()

        # High count should have been bumped by confidence_bump (0.02)
        assert high_row["confidence"] > 0.5
        # Low count should remain unchanged
        assert low_row["confidence"] == 0.5

    # -------------------------------------------------------------------------
    # Test 4: Decay of stale patterns
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_decay_of_stale_patterns(
        self, refiner, mock_memory, in_memory_db
    ):
        """Patterns not reinforced for N days get confidence decrement."""
        now = time.time()
        stale_days = 30

        # Insert two patterns: one stale (>30 days), one recent
        # Both have reinforcement_count below threshold so they don't get reinforced
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-stale", "Stale pattern", "", 0.6,
                "[]", 0, now, now - (stale_days + 5) * 86400, 4, now,
            ),
        )
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-recent", "Recent pattern", "", 0.6,
                "[]", 0, now, now - 5 * 86400, 4, now,
            ),
        )

        result = await refiner.refine()

        stale_row = in_memory_db.execute(
            "SELECT confidence FROM procedural_memory WHERE pattern_id = ?",
            ("pattern-stale",),
        ).fetchone()
        recent_row = in_memory_db.execute(
            "SELECT confidence FROM procedural_memory WHERE pattern_id = ?",
            ("pattern-recent",),
        ).fetchone()

        # Stale should have been decayed (0.6 - 0.01 = 0.59)
        assert stale_row["confidence"] < 0.6
        # Recent has reinforcement_count < threshold so it doesn't get reinforced
        assert recent_row["confidence"] == 0.6

    # -------------------------------------------------------------------------
    # Test 5: Archival of low-confidence patterns
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_archive_low_confidence(
        self, refiner, mock_memory, in_memory_db
    ):
        """Patterns with confidence below archive_threshold are deleted."""
        now = time.time()

        # Insert two patterns: one below threshold (0.1), one above
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-low-conf", "Low confidence pattern", "", 0.05,
                "[]", 0, now, now, 1, now,
            ),
        )
        in_memory_db.execute(
            """INSERT INTO procedural_memory
               (pattern_id, description, trigger_context, confidence,
                evidence_episode_ids, evidence_count, first_observed,
                last_reinforced, reinforcement_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pattern-high-conf", "High confidence pattern", "", 0.5,
                "[]", 0, now, now, 1, now,
            ),
        )

        result = await refiner.refine()

        remaining = in_memory_db.execute(
            "SELECT COUNT(*) as c FROM procedural_memory"
        ).fetchone()["c"]

        assert remaining == 1
        # The only remaining pattern should be the high-confidence one
        remaining_id = in_memory_db.execute(
            "SELECT pattern_id FROM procedural_memory"
        ).fetchone()["pattern_id"]
        assert remaining_id == "pattern-high-conf"

    # -------------------------------------------------------------------------
    # Test 6: Event emission
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_event_emission(self, refiner, mock_event_bus):
        """Events are published for start, refined, and complete."""
        await refiner.refine()

        published_events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
        assert "sleep.consolidation.procedural_refiner.start" in published_events
        assert "sleep.consolidation.procedural_refined" in published_events