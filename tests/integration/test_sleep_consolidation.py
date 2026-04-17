"""Integration tests for sleep consolidation flow.

Tests the full path:
- SleepScheduler → ConsolidationEngine → MemoryArchitecture

Uses real in-memory SQLite for MemoryArchitecture, real ConsolidationEngine,
and mock InferenceGateway that returns 3 facts.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.sleep.consolidation import ConsolidationEngine
from sentient.sleep.schemas import (
    ExtractedFact,
    ExtractedPattern,
    ProceduralPatternList,
    SemanticFactList,
)
from sentient.sleep.scheduler import SleepScheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with full schema."""
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
            archived_at REAL,
            consolidation_weight REAL DEFAULT 0.0
        );

        CREATE TABLE consolidation_log (
            id TEXT PRIMARY KEY,
            consolidated_at REAL NOT NULL,
            scope TEXT NOT NULL,
            summary_content TEXT,
            source_memory_count INTEGER,
            coverage_start REAL,
            coverage_end REAL
        );

        CREATE TABLE semantic_memory (
            id TEXT PRIMARY KEY,
            fact_id TEXT NOT NULL UNIQUE,
            statement TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.7,
            evidence_episode_ids TEXT NOT NULL DEFAULT '[]',
            evidence_count INTEGER NOT NULL DEFAULT 0,
            first_observed REAL NOT NULL,
            last_reinforced REAL NOT NULL,
            reinforcement_count INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE procedural_memory (
            id TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            trigger_context TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.6,
            evidence_episode_ids TEXT NOT NULL DEFAULT '[]',
            evidence_count INTEGER NOT NULL DEFAULT 0,
            first_observed REAL NOT NULL,
            last_reinforced REAL NOT NULL,
            reinforcement_count INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE INDEX idx_semantic_confidence ON semantic_memory(confidence);
        CREATE INDEX idx_semantic_active ON semantic_memory(is_active);
        CREATE INDEX idx_procedural_confidence ON procedural_memory(confidence);
        CREATE INDEX idx_procedural_active ON procedural_memory(is_active);
    """)
    return conn


@pytest.fixture
def mock_memory_architecture(in_memory_db):
    """Create a real MemoryArchitecture with in-memory SQLite and mocked ChromaDB."""
    from sentient.memory.semantic import SemanticStore
    from sentient.memory.procedural import ProceduralStore

    arch = MagicMock()
    arch._conn = in_memory_db
    arch.semantic_store = SemanticStore(in_memory_db)
    arch.procedural_store = ProceduralStore(in_memory_db)

    return arch


@pytest.fixture
def mock_gateway_with_3_facts():
    """Mock InferenceGateway that returns 3 semantic facts from LLM."""
    gateway = MagicMock()

    semantic_response = AsyncMock()
    semantic_response.error = None
    semantic_response.text = SemanticFactList(
        facts=[
            ExtractedFact(
                statement="The creator prefers Python for most tasks.",
                confidence=0.85,
                evidence_episode_ids=["ep-1", "ep-2", "ep-3"],
            ),
            ExtractedFact(
                statement="Long conversations happen frequently.",
                confidence=0.78,
                evidence_episode_ids=["ep-1", "ep-4", "ep-5"],
            ),
            ExtractedFact(
                statement="Testing is considered important.",
                confidence=0.82,
                evidence_episode_ids=["ep-2", "ep-3", "ep-6"],
            ),
        ]
    ).model_dump_json()

    procedural_response = AsyncMock()
    procedural_response.error = None
    procedural_response.text = ProceduralPatternList(patterns=[]).model_dump_json()

    gateway.infer = AsyncMock(side_effect=[semantic_response, procedural_response])
    return gateway


@pytest.fixture
def mock_event_bus():
    """Mock EventBus with async publish."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_lifecycle():
    """Mock lifecycle manager."""
    lc = MagicMock()
    lc.pause_for_sleep = AsyncMock()
    lc.resume_from_sleep = AsyncMock()
    return lc


@pytest.fixture
def scheduler_with_consolidation(
    mock_memory_architecture, mock_gateway_with_3_facts, mock_event_bus, mock_lifecycle
):
    """SleepScheduler wired with real ConsolidationEngine."""
    consolidation_engine = ConsolidationEngine(
        memory_architecture=mock_memory_architecture,
        inference_gateway=mock_gateway_with_3_facts,
        event_bus=mock_event_bus,
        config={
            "min_new_episodes": 3,
            "confidence_threshold_semantic": 0.7,
            "confidence_threshold_procedural": 0.6,
            "llm_call_timeout_seconds": 30,
            "semantic_similarity_threshold": 0.9,
            "consolidation_weight_bump": 0.1,
        },
    )

    config = {
        "duration": {"min_hours": 6, "max_hours": 12},
        "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
        "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
        "consolidation_enabled": True,
    }

    scheduler = SleepScheduler(
        config,
        mock_lifecycle,
        memory=mock_memory_architecture,
        consolidation_engine=consolidation_engine,
        event_bus=mock_event_bus,
    )
    scheduler._sleep_cycle_count = 1
    return scheduler


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ep(id_suffix: str, created_at: float, content: str) -> dict[str, Any]:
    return {
        "id": f"ep-{id_suffix}",
        "memory_type": "episodic",
        "content": content,
        "content_hash": f"hash-{id_suffix}",
        "importance": 0.5,
        "confidence": 1.0,
        "created_at": created_at,
        "is_archived": 0,
        "entity_tags": "[]",
        "topic_tags": "[]",
        "emotional_tags": "{}",
        "metadata": "{}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSleepConsolidationIntegration:
    """Integration tests for SleepScheduler → ConsolidationEngine flow."""

    @pytest.mark.asyncio
    async def test_post_cycle_facts_in_semantic_store(
        self, scheduler_with_consolidation, mock_memory_architecture, in_memory_db
    ):
        """After deep consolidation, facts are stored in the semantic store."""
        now = time.time()
        # Insert 6 episodes that will be processed
        for i in range(1, 7):
            in_memory_db.execute(
                """
                INSERT INTO memories (id, memory_type, content, content_hash, importance,
                    confidence, created_at, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"ep-{i}", "episodic", f"Episode {i} content", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
            )

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler_with_consolidation._run_deep_consolidation(5)

        # Verify facts were stored
        rows = in_memory_db.execute(
            "SELECT fact_id, statement, confidence, evidence_count FROM semantic_memory WHERE is_active = 1"
        ).fetchall()

        assert len(rows) == 3, f"Expected 3 facts, got {len(rows)}: {rows}"
        statements = [row["statement"] for row in rows]
        assert any("Python" in s for s in statements)
        assert any("conversations" in s or "Long" in s for s in statements)
        assert any("Testing" in s for s in statements)

    @pytest.mark.asyncio
    async def test_consolidation_cycle_publishes_events(
        self, scheduler_with_consolidation, mock_event_bus, in_memory_db
    ):
        """Deep consolidation publishes the expected events."""
        now = time.time()
        for i in range(1, 7):
            in_memory_db.execute(
                """
                INSERT INTO memories (id, memory_type, content, content_hash, importance,
                    confidence, created_at, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"ep-{i}", "episodic", f"Episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
            )

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler_with_consolidation._run_deep_consolidation(5)

        # Verify events were published
        published_events = [call.args[0] for call in mock_event_bus.publish.call_args_list]

        assert "sleep.deep_consolidation.start" in published_events
        assert "sleep.consolidation.cycle_start" in published_events
        assert "sleep.consolidation.cycle_complete" in published_events

    @pytest.mark.asyncio
    async def test_consolidation_skipped_when_insufficient_episodes(
        self, mock_memory_architecture, mock_gateway_with_3_facts, mock_event_bus, mock_lifecycle
    ):
        """With < min_new_episodes, consolidation is skipped and cycle_complete not published."""
        consolidation_engine = ConsolidationEngine(
            memory_architecture=mock_memory_architecture,
            inference_gateway=mock_gateway_with_3_facts,
            event_bus=mock_event_bus,
            config={
                "min_new_episodes": 6,  # need 6, but only inserting 3
                "confidence_threshold_semantic": 0.7,
                "confidence_threshold_procedural": 0.6,
                "llm_call_timeout_seconds": 30,
                "semantic_similarity_threshold": 0.9,
                "consolidation_weight_bump": 0.1,
            },
        )

        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "consolidation_enabled": True,
        }

        scheduler = SleepScheduler(
            config,
            mock_lifecycle,
            memory=mock_memory_architecture,
            consolidation_engine=consolidation_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        # Insert only 3 episodes (below the 6 threshold)
        in_memory_db = mock_memory_architecture._conn
        now = time.time()
        for i in range(1, 4):
            in_memory_db.execute(
                """
                INSERT INTO memories (id, memory_type, content, content_hash, importance,
                    confidence, created_at, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"ep-{i}", "episodic", f"Episode {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
            )

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_deep_consolidation(5)

        # Should have published skipped event instead
        published_events = [call.args[0] for call in mock_event_bus.publish.call_args_list]
        assert "sleep.consolidation.skipped" in published_events
        # cycle_complete should NOT be published when skipped
        assert "sleep.consolidation.cycle_complete" not in published_events
