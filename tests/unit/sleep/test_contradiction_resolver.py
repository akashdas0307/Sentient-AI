"""Unit tests for ContradictionResolver."""

from __future__ import annotations

import sqlite3
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestContradictionResolver:
    """Tests for ContradictionResolver (Job 2 of sleep consolidation)."""

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
            CREATE TABLE contradictions (
                id TEXT PRIMARY KEY,
                memory_a_id TEXT NOT NULL,
                memory_b_id TEXT NOT NULL,
                detected_at REAL NOT NULL,
                resolved_at REAL,
                resolution TEXT,
                notes TEXT
            );
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
    def mock_gateway(self):
        """Mock inference gateway."""
        gw = MagicMock()
        gw.infer = AsyncMock()
        return gw

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus with async publish."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        yield bus
        bus.reset_mock()

    @pytest.fixture
    def resolver(self, mock_memory, mock_gateway, mock_event_bus):
        """ContradictionResolver with default config.

        The resolver's mock_memory._conn is set to in_memory_db from
        the resolver's own fixture chain (mock_memory -> in_memory_db).
        Tests access the same DB via mock_memory._conn.
        """
        from sentient.sleep.contradiction_resolver import ContradictionResolver
        return ContradictionResolver(
            memory_architecture=mock_memory,
            inference_gateway=mock_gateway,
            event_bus=mock_event_bus,
            config={},
        )

    # -------------------------------------------------------------------------
    # Test 1: Initialization with config
    # -------------------------------------------------------------------------

    def test_init_with_config(self, mock_memory, mock_gateway, mock_event_bus):
        """Resolver initializes with custom config values."""
        from sentient.sleep.contradiction_resolver import (
            ContradictionResolver,
            DEFAULT_ENABLED,
            DEFAULT_MAX_PAIRS_PER_CYCLE,
            DEFAULT_SIMILARITY_THRESHOLD,
            DEFAULT_LLM_TIMEOUT_SECONDS,
        )
        config = {
            "enabled": False,
            "max_pairs_per_cycle": 5,
            "similarity_threshold": 0.5,
            "llm_timeout_seconds": 15,
        }
        r = ContradictionResolver(
            memory_architecture=mock_memory,
            inference_gateway=mock_gateway,
            event_bus=mock_event_bus,
            config=config,
        )
        assert r._enabled is False
        assert r._max_pairs_per_cycle == 5
        assert r._similarity_threshold == 0.5
        assert r._llm_timeout == 15

    # -------------------------------------------------------------------------
    # Test 2: Disabled resolver returns skipped status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(self, mock_memory, mock_gateway, mock_event_bus):
        """When enabled=False, resolve_contradictions returns skipped status."""
        from sentient.sleep.contradiction_resolver import ContradictionResolver
        r = ContradictionResolver(
            memory_architecture=mock_memory,
            inference_gateway=mock_gateway,
            event_bus=mock_event_bus,
            config={"enabled": False},
        )
        result = await r.resolve_contradictions()
        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    # -------------------------------------------------------------------------
    # Test 3: Jaccard similarity calculation
    # -------------------------------------------------------------------------

    def test_jaccard_similarity(self, resolver):
        """Jaccard similarity correctly computed for identical and disjoint texts."""
        # Identical texts
        text = "the quick brown fox jumps over the lazy dog"
        assert resolver._jaccard_similarity(text, text) == 1.0

        # Partial overlap
        a = "the quick brown fox"
        b = "the quick red fox"
        sim = resolver._jaccard_similarity(a, b)
        assert 0.0 < sim < 1.0

        # No overlap
        a = "the quick brown fox jumps over the lazy dog"
        b = "hello world"
        assert resolver._jaccard_similarity(a, b) == 0.0

        # Empty text
        assert resolver._jaccard_similarity("", "hello") == 0.0
        assert resolver._jaccard_similarity("hello", "") == 0.0
        assert resolver._jaccard_similarity("", "") == 0.0

    # -------------------------------------------------------------------------
    # Test 4: Contradiction detection via mock LLM
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_contradiction_detection_with_mock_llm(
        self, resolver, mock_gateway, in_memory_db
    ):
        """LLM is called and contradiction correctly identified from response."""
        # Inject two episodic memories with different confidence
        now = time.time()
        in_memory_db.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-a", "I like coffee", "hash-a", 0.5, 1.0, now - 3600),
        )
        in_memory_db.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-b", "I don't like coffee", "hash-b", 0.5, 1.0, now - 7200),
        )

        # Mock LLM returns a contradiction detection
        mock_gateway.infer = AsyncMock(
            return_value=MagicMock(
                text='{"contradicts": true, "resolution": "a_supersedes", "notes": "Negation detected"}',
                error=None,
            )
        )

        result = await resolver.resolve_contradictions()
        assert result["status"] == "completed"
        assert result["pairs_checked"] >= 1
        assert result["contradictions_found"] >= 1

    # -------------------------------------------------------------------------
    # Test 5: Resolution storage in contradictions table
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_resolution_stored_in_contradictions_table(
        self, resolver, mock_gateway, mock_memory
    ):
        """When a contradiction is confirmed, it is written to the contradictions table."""
        now = time.time()
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-x", "The sky is blue today", "hash-x", 0.6, 1.0, now - 1800),
        )
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-y", "The sky is not blue today", "hash-y", 0.6, 1.0, now - 900),
        )

        mock_gateway.infer = AsyncMock(
            return_value=MagicMock(
                text='{"contradicts": true, "resolution": "a_supersedes", "notes": "One is negated"}',
                error=None,
            )
        )

        await resolver.resolve_contradictions()

        # The pair (mem-y, mem-x) is produced by _generate_candidate_pairs,
        # and "a_supersedes" means memory_a (mem-y) supersedes memory_b (mem-x).
        # So we query for memory_b_id = 'mem-x'.
        rows = mock_memory._conn.execute(
            "SELECT * FROM contradictions WHERE memory_b_id = 'mem-x'"
        ).fetchall()
        assert len(rows) >= 1
        row = rows[0]
        # memory_a is the newer memory (mem-y), memory_b is the older (mem-x)
        assert row["memory_b_id"] == "mem-x"
        assert row["resolution"] == "a_supersedes"

    # -------------------------------------------------------------------------
    # Test 6: Confidence reduction for superseded memories
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_confidence_reduction_for_superseded(
        self, resolver, mock_gateway, mock_memory
    ):
        """When a_supersedes is resolved, the older memory's confidence is multiplied by 0.7."""
        now = time.time()
        original_confidence = 1.0
        # mem-alpha (older) has no negation, mem-beta (newer) has negation.
        # Pair from _generate_candidate_pairs: (mem-beta, mem-alpha) — newer first.
        # "a_supersedes" → newer (mem-beta) supersedes older (mem-alpha).
        # mem-alpha's confidence should be reduced, mem-beta's stays 1.0.
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-alpha", "X is correct", "hash-alpha", 0.5, original_confidence, now - 1200),
        )
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("mem-beta", "X is not correct", "hash-beta", 0.5, 1.0, now - 600),
        )

        mock_gateway.infer = AsyncMock(
            return_value=MagicMock(
                text='{"contradicts": true, "resolution": "a_supersedes", "notes": "Beta is wrong"}',
                error=None,
            )
        )

        await resolver.resolve_contradictions()

        # The older memory (mem-alpha) is superseded and gets reduced confidence
        row_alpha = mock_memory._conn.execute(
            "SELECT confidence FROM memories WHERE id = 'mem-alpha'"
        ).fetchone()
        assert row_alpha is not None
        assert row_alpha["confidence"] == pytest.approx(original_confidence * 0.7, abs=0.01)

        # The newer memory (mem-beta) is not superseded, stays at 1.0
        row_beta = mock_memory._conn.execute(
            "SELECT confidence FROM memories WHERE id = 'mem-beta'"
        ).fetchone()
        assert row_beta is not None
        assert row_beta["confidence"] == 1.0

    # -------------------------------------------------------------------------
    # Test 7: max_pairs_per_cycle limit is respected
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_max_pairs_per_cycle_limit(
        self, mock_memory, mock_gateway, mock_event_bus, in_memory_db
    ):
        """When candidate pairs exceed max_pairs_per_cycle, only that many are checked."""
        from sentient.sleep.contradiction_resolver import ContradictionResolver

        now = time.time()
        # Insert many memories that would generate candidates
        for i in range(30):
            in_memory_db.execute(
                """
                INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
                VALUES (?, 'episodic', ?, ?, ?, ?, ?)
                """,
                (f"mem-{i:03d}", f"content word-{i} not correct statement", f"hash-{i}", 0.6, 1.0, now - i * 60),
            )

        r = ContradictionResolver(
            memory_architecture=mock_memory,
            inference_gateway=mock_gateway,
            event_bus=mock_event_bus,
            config={"max_pairs_per_cycle": 5, "similarity_threshold": 0.1},
        )
        mock_gateway.infer = AsyncMock(
            return_value=MagicMock(
                text='{"contradicts": false, "resolution": null, "notes": ""}',
                error=None,
            )
        )

        result = await r.resolve_contradictions()
        # Should be capped at 5
        assert result["pairs_checked"] <= 5

    # -------------------------------------------------------------------------
    # Test 8: Event emission
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_event_emission(self, resolver, mock_gateway, mock_event_bus, mock_memory):
        """Events are published for start, contradiction_resolved, and complete."""
        now = time.time()
        # Use clear negation signals: "I agree" (no negation) vs "I do not agree" (has "not")
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("ev-a", "I agree with this plan", "hash-ev-a", 0.5, 1.0, now - 3600),
        )
        mock_memory._conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at)
            VALUES (?, 'episodic', ?, ?, ?, ?, ?)
            """,
            ("ev-b", "I do not agree with this plan", "hash-ev-b", 0.5, 1.0, now - 1800),
        )

        mock_gateway.infer = AsyncMock(
            return_value=MagicMock(
                text='{"contradicts": true, "resolution": "both_valid", "notes": "Different contexts"}',
                error=None,
            )
        )

        await resolver.resolve_contradictions()

        # Check that publish was called at least 3 times (start, resolved, complete)
        assert mock_event_bus.publish.call_count >= 3

        # Verify specific event names
        published_events = [call[0][0] for call in mock_event_bus.publish.call_args_list]
        assert "sleep.consolidation.contradiction_resolver.start" in published_events
        assert "sleep.consolidation.contradiction_resolved" in published_events
        assert "sleep.consolidation.contradiction_resolver.complete" in published_events
