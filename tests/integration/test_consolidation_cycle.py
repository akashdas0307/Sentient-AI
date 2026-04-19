"""Integration tests for consolidation cycle.

Uses real in-memory SQLite for MemoryArchitecture, real ConsolidationEngine,
and mock InferenceGateway that returns structured output. No real LLM calls.

Run with: pytest tests/integration/ -v -k "consolidation_cycle"
"""
from __future__ import annotations

import json
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.sleep.consolidation import ConsolidationEngine
from sentient.sleep.schemas import (
    ExtractedFact,
    ExtractedPattern,
    ProceduralPatternList,
    SemanticFactList,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(text: str) -> MagicMock:
    """Create a mock InferenceResponse with the given text."""
    resp = MagicMock()
    resp.error = None
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
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
            archived_at REAL,
            consolidation_weight REAL DEFAULT 0.0
        );
        CREATE INDEX idx_memory_type ON memories(memory_type);
        CREATE INDEX idx_created_at ON memories(created_at);
        CREATE INDEX idx_archived ON memories(is_archived);

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
            fact_id TEXT PRIMARY KEY,
            statement TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            evidence_episode_ids TEXT NOT NULL DEFAULT '[]',
            evidence_count INTEGER NOT NULL DEFAULT 0,
            first_observed REAL NOT NULL,
            last_reinforced REAL NOT NULL,
            reinforcement_count INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );
        CREATE INDEX idx_semantic_confidence ON semantic_memory(confidence);

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
        CREATE INDEX idx_procedural_confidence ON procedural_memory(confidence);
    """)
    return conn


@pytest.fixture
def memory_arch(in_memory_db):
    """MemoryArchitecture with in-memory SQLite, real SemanticStore/ProceduralStore."""
    from sentient.memory.semantic import SemanticStore
    from sentient.memory.procedural import ProceduralStore

    arch = MagicMock()
    arch._conn = in_memory_db
    arch.semantic_store = SemanticStore(in_memory_db)
    arch.procedural_store = ProceduralStore(in_memory_db)
    # Use real stores so _find_similar_* methods work
    return arch


@pytest.fixture
def mock_gateway_with_facts_and_patterns():
    """Mock InferenceGateway returning structured SemanticFactList + ProceduralPatternList."""
    semantic_json = SemanticFactList(
        facts=[
            ExtractedFact(
                statement="Akash is the creator and primary user of this system.",
                confidence=0.85,
                evidence_episode_ids=["ep-1", "ep-2", "ep-3"],
            ),
            ExtractedFact(
                statement="Akash has a background in biology.",
                confidence=0.80,
                evidence_episode_ids=["ep-4", "ep-5", "ep-6"],
            ),
        ],
    ).model_dump_json()

    procedural_json = ProceduralPatternList(
        patterns=[
            ExtractedPattern(
                description="Akash prefers iterative, module-by-module development.",
                trigger_context="When discussing project planning or architecture.",
                confidence=0.75,
                evidence_episode_ids=["ep-1", "ep-3", "ep-5"],
            ),
        ],
    ).model_dump_json()

    gateway = MagicMock()
    semantic_response = MagicMock()
    semantic_response.error = None
    semantic_response.text = semantic_json

    procedural_response = MagicMock()
    procedural_response.error = None
    procedural_response.text = procedural_json

    gateway.infer = AsyncMock(side_effect=[semantic_response, procedural_response])
    return gateway


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def consolidation_engine(memory_arch, mock_gateway_with_facts_and_patterns, mock_event_bus):
    return ConsolidationEngine(
        memory_architecture=memory_arch,
        inference_gateway=mock_gateway_with_facts_and_patterns,
        event_bus=mock_event_bus,
        config={
            "min_new_episodes": 6,
            "confidence_threshold_semantic": 0.7,
            "confidence_threshold_procedural": 0.6,
            "llm_call_timeout_seconds": 30,
            "semantic_similarity_threshold": 0.9,
            "consolidation_weight_bump": 0.1,
        },
    )


def _insert_episodes(conn: sqlite3.Connection, count: int = 6, start_time: float | None = None):
    """Insert `count` episodic memories into the in-memory DB."""
    now = start_time or time.time()
    for i in range(1, count + 1):
        ep_id = f"ep-{i}"
        content = f"Episode {i} content for testing consolidation."
        content_hash = f"hash-{i}"
        conn.execute(
            """
            INSERT INTO memories (id, memory_type, content, content_hash, importance,
                confidence, created_at, is_archived, entity_tags, topic_tags,
                emotional_tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ep_id, "episodic", content, content_hash, 0.5, 1.0,
                now - (count - i) * 10, 0,
                "[]", "[]", "{}", "{}",
            ),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConsolidationCycleIntegration:
    """Integration tests for consolidation cycle using mock InferenceGateway.

    These tests run with: pytest tests/integration/ -v
    They do NOT require Ollama or real LLM calls.
    """

    @pytest.mark.asyncio
    async def test_consolidate_cycle_stores_facts(self, consolidation_engine, in_memory_db):
        """Verify that consolidation stores semantic facts in the semantic_store."""
        _insert_episodes(in_memory_db)

        result = await consolidation_engine.consolidate_cycle()

        assert result["status"] == "completed"
        assert result["facts_extracted"] == 2

        rows = in_memory_db.execute(
            "SELECT fact_id, statement, confidence, evidence_count FROM semantic_memory"
        ).fetchall()
        assert len(rows) == 2
        statements = [row["statement"] for row in rows]
        assert any("Akash" in s for s in statements)
        assert any("biology" in s for s in statements)

    @pytest.mark.asyncio
    async def test_consolidate_cycle_stores_patterns(self, consolidation_engine, in_memory_db):
        """Verify that consolidation stores procedural patterns in the procedural_store."""
        _insert_episodes(in_memory_db)

        result = await consolidation_engine.consolidate_cycle()

        assert result["status"] == "completed"
        assert result["patterns_extracted"] == 1

        rows = in_memory_db.execute(
            "SELECT pattern_id, description, confidence FROM procedural_memory"
        ).fetchall()
        assert len(rows) == 1
        assert "iterative" in rows[0]["description"] or "module" in rows[0]["description"]

    @pytest.mark.asyncio
    async def test_consolidate_cycle_skips_insufficient_episodes(
        self, memory_arch, mock_gateway_with_facts_and_patterns, mock_event_bus, in_memory_db
    ):
        """Verify consolidation skips when < 6 new episodes exist."""
        engine = ConsolidationEngine(
            memory_architecture=memory_arch,
            inference_gateway=mock_gateway_with_facts_and_patterns,
            event_bus=mock_event_bus,
            config={
                "min_new_episodes": 6,
                "confidence_threshold_semantic": 0.7,
                "confidence_threshold_procedural": 0.6,
                "llm_call_timeout_seconds": 30,
                "semantic_similarity_threshold": 0.9,
                "consolidation_weight_bump": 0.1,
            },
        )

        _insert_episodes(in_memory_db, count=3)

        result = await engine.consolidate_cycle()

        assert result["status"] == "skipped"
        assert result["reason"] == "insufficient_episodes"
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_consolidate_cycle_reinforces_existing_facts(
        self, memory_arch, mock_event_bus, in_memory_db
    ):
        """Verify second consolidation run reinforces existing facts rather than duplicating."""
        # First run
        semantic_json_1 = SemanticFactList(
            facts=[
                ExtractedFact(
                    statement="Akash is the creator.",
                    confidence=0.85,
                    evidence_episode_ids=["ep-1", "ep-2", "ep-3"],
                ),
            ],
        ).model_dump_json()

        proc_json_1 = ProceduralPatternList(patterns=[]).model_dump_json()

        gateway_1 = MagicMock()
        gateway_1.infer = AsyncMock(side_effect=[
            _mock_response(semantic_json_1),
            _mock_response(proc_json_1),
        ])

        engine_1 = ConsolidationEngine(
            memory_architecture=memory_arch,
            inference_gateway=gateway_1,
            event_bus=mock_event_bus,
            config={
                "min_new_episodes": 6,
                "confidence_threshold_semantic": 0.7,
                "confidence_threshold_procedural": 0.6,
                "llm_call_timeout_seconds": 30,
                "semantic_similarity_threshold": 0.9,
                "consolidation_weight_bump": 0.1,
            },
        )

        _insert_episodes(in_memory_db, count=6)
        result_1 = await engine_1.consolidate_cycle()
        assert result_1["status"] == "completed"

        rows_before = in_memory_db.execute(
            "SELECT fact_id, reinforcement_count FROM semantic_memory"
        ).fetchall()
        assert len(rows_before) == 1
        first_r_count = rows_before[0]["reinforcement_count"]

        # Second run with new episodes — return same fact (reinforces, not duplicate)
        # The LLM may reference episodes from the first batch too; validation filters to only-new ones
        semantic_json_2 = SemanticFactList(
            facts=[
                ExtractedFact(
                    statement="Akash is the creator.",
                    confidence=0.88,
                    # ep-7 and ep-8 are in the second batch; ep-1 and ep-2 are from first (filtered out)
                    evidence_episode_ids=["ep-1", "ep-7", "ep-8"],
                ),
            ],
        ).model_dump_json()

        proc_json_2 = ProceduralPatternList(patterns=[]).model_dump_json()

        gateway_2 = MagicMock()
        gateway_2.infer = AsyncMock(side_effect=[
            _mock_response(semantic_json_2),
            _mock_response(proc_json_2),
        ])

        engine_2 = ConsolidationEngine(
            memory_architecture=memory_arch,
            inference_gateway=gateway_2,
            event_bus=mock_event_bus,
            config={
                "min_new_episodes": 6,
                "confidence_threshold_semantic": 0.7,
                "confidence_threshold_procedural": 0.6,
                "llm_call_timeout_seconds": 30,
                "semantic_similarity_threshold": 0.9,
                "consolidation_weight_bump": 0.1,
            },
        )

        # Add new episodes with timestamps AFTER the first consolidation
        now = time.time() + 100  # well after first batch (which uses now)
        for i in range(7, 13):
            in_memory_db.execute(
                """
                INSERT INTO memories (id, memory_type, content, content_hash, importance,
                    confidence, created_at, is_archived, entity_tags, topic_tags,
                    emotional_tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ep-{i}", "episodic", f"Episode {i} reinforcing content.", f"hash-{i}",
                    0.5, 1.0, now + (i - 6) * 10, 0,
                    "[]", "[]", "{}", "{}",
                ),
            )

        result_2 = await engine_2.consolidate_cycle()
        assert result_2["status"] == "completed"

        rows_after = in_memory_db.execute(
            "SELECT fact_id, reinforcement_count, evidence_count FROM semantic_memory"
        ).fetchall()
        assert len(rows_after) == 1
        assert rows_after[0]["reinforcement_count"] >= first_r_count + 1

    @pytest.mark.asyncio
    async def test_consolidation_log_recorded(self, consolidation_engine, in_memory_db):
        """Verify that consolidation_log table has a record after the run."""
        _insert_episodes(in_memory_db)

        await consolidation_engine.consolidate_cycle()

        rows = in_memory_db.execute(
            "SELECT id, consolidated_at, scope, summary_content, source_memory_count FROM consolidation_log"
        ).fetchall()

        assert len(rows) == 1
        assert rows[0]["scope"] == "daily"
        assert rows[0]["source_memory_count"] == 6

        summary = json.loads(rows[0]["summary_content"])
        assert "semantic_facts_extracted" in summary
        assert "procedural_patterns_extracted" in summary

    @pytest.mark.asyncio
    async def test_consolidation_events_published(
        self, consolidation_engine, mock_event_bus, in_memory_db
    ):
        """Verify that consolidation publishes cycle_start and cycle_complete events."""
        _insert_episodes(in_memory_db)

        await consolidation_engine.consolidate_cycle()

        published_events = [call.args[0] for call in mock_event_bus.publish.call_args_list]
        assert "sleep.consolidation.cycle_start" in published_events
        assert "sleep.consolidation.cycle_complete" in published_events