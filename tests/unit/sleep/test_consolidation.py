"""Unit tests for ConsolidationEngine."""

from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.sleep.consolidation import (
    DEFAULT_CONSOLIDATION_WEIGHT_BUMP,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_MIN_EPISODES,
    DEFAULT_PROCEDURAL_CONFIDENCE_THRESHOLD,
    DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    ConsolidationEngine,
)
from sentient.sleep.schemas import (
    ExtractedFact,
    ExtractedPattern,
    ProceduralPatternList,
    SemanticFactList,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with the required schema."""
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
    """)
    return conn


@pytest.fixture
def mock_gateway():
    """Create a mock InferenceGateway."""
    gateway = MagicMock()
    gateway.infer = AsyncMock()
    return gateway


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_memory_architecture(in_memory_db, monkeypatch):
    """Create a mock MemoryArchitecture with real in-memory SQLite stores."""
    from sentient.memory.semantic import SemanticStore
    from sentient.memory.procedural import ProceduralStore

    arch = MagicMock()
    arch._conn = in_memory_db
    arch.semantic_store = SemanticStore(in_memory_db)
    arch.procedural_store = ProceduralStore(in_memory_db)

    return arch


@pytest.fixture
def engine(mock_memory_architecture, mock_gateway, mock_event_bus):
    """Create a ConsolidationEngine with mocked dependencies."""
    config = {
        "min_new_episodes": DEFAULT_MIN_EPISODES,
        "confidence_threshold_semantic": DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD,
        "confidence_threshold_procedural": DEFAULT_PROCEDURAL_CONFIDENCE_THRESHOLD,
        "llm_call_timeout_seconds": DEFAULT_LLM_TIMEOUT_SECONDS,
        "semantic_similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "consolidation_weight_bump": DEFAULT_CONSOLIDATION_WEIGHT_BUMP,
    }
    return ConsolidationEngine(
        memory_architecture=mock_memory_architecture,
        inference_gateway=mock_gateway,
        event_bus=mock_event_bus,
        config=config,
    )


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
# Tests: consolidate_cycle — skipped path
# ---------------------------------------------------------------------------

def test_consolidate_cycle_skipped_insufficient_episodes(engine, in_memory_db):
    """When < 6 new episodes exist, consolidation is skipped."""
    now = time.time()
    # Insert only 3 episodes all dated before any consolidation
    for i in range(3):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"old-ep-{i}", "episodic", f"content {i}", f"hash{i}", 0.5, 1.0, now - 1000 - i, 0),
        )

    result = asyncio.run(engine.consolidate_cycle())

    assert result["status"] == "skipped"
    assert result["reason"] == "insufficient_episodes"
    # All 3 episodes are "new" (no consolidation has ever run, so last_consolidation_time = 0)
    assert result["count"] == 3


# ---------------------------------------------------------------------------
# Tests: consolidate_cycle — happy path
# ---------------------------------------------------------------------------

def test_consolidate_cycle_runs_both_extractions(engine, mock_gateway, in_memory_db):
    """When >= 6 episodes exist, both extractions are called."""
    now = time.time()
    for i in range(6):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode content {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    # Mock LLM responses
    semantic_response = AsyncMock()
    semantic_response.error = None
    semantic_response.text = SemanticFactList(
        facts=[
            ExtractedFact(
                statement="This is a factual statement.",
                confidence=0.85,
                evidence_episode_ids=["ep-0", "ep-1"],
            )
        ]
    ).model_dump_json()

    procedural_response = AsyncMock()
    procedural_response.error = None
    procedural_response.text = ProceduralPatternList(
        patterns=[
            ExtractedPattern(
                description="A behavioral pattern.",
                trigger_context="When working.",
                confidence=0.75,
                evidence_episode_ids=["ep-0", "ep-1"],
            )
        ]
    ).model_dump_json()

    mock_gateway.infer = AsyncMock(side_effect=[semantic_response, procedural_response])

    result = asyncio.run(engine.consolidate_cycle())

    assert result["status"] == "completed"
    assert result["facts_extracted"] == 1
    assert result["patterns_extracted"] == 1
    assert result["episodes_processed"] == 6

    # Verify event bus publish calls
    engine.event_bus.publish.assert_any_call(
        "sleep.consolidation.cycle_start", {"episode_count": 6}
    )
    # Check cycle_complete call arguments
    complete_call = None
    for call in engine.event_bus.publish.call_args_list:
        if call.args and call.args[0] == "sleep.consolidation.cycle_complete":
            complete_call = call
            break
    assert complete_call is not None, "cycle_complete event not published"
    payload = complete_call.args[1]
    assert payload["facts_extracted"] == 1
    assert payload["patterns_extracted"] == 1
    assert payload["episodes_processed"] == 6


# ---------------------------------------------------------------------------
# Tests: LLM timeout handling
# ---------------------------------------------------------------------------

async def test_semantic_timeout_continues_to_procedural(engine, mock_gateway, in_memory_db):
    """Semantic timeout skips semantic but still runs procedural extraction."""
    now = time.time()
    for i in range(6):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"episode content {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    # First call times out, second call succeeds
    semantic_response = AsyncMock()
    semantic_response.error = "timeout"
    semantic_response.text = ""

    procedural_response = AsyncMock()
    procedural_response.error = None
    procedural_response.text = ProceduralPatternList(patterns=[]).model_dump_json()

    mock_gateway.infer = AsyncMock(side_effect=[semantic_response, procedural_response])

    result = await engine.consolidate_cycle()

    assert result["status"] == "completed"
    assert result["facts_extracted"] == 0
    assert result["patterns_extracted"] == 0


# ---------------------------------------------------------------------------
# Tests: Post-validation — low evidence rejection
# ---------------------------------------------------------------------------

def test_post_validation_drops_single_episode_facts(engine, in_memory_db):
    """Facts with evidence from only 1 episode are dropped."""
    fact = ExtractedFact(
        statement="Only appears once.",
        confidence=0.9,
        evidence_episode_ids=["ep-0"],  # only 1
    )
    episodes = [_ep("0", time.time(), "content")]
    validated = engine._post_validate_semantic([fact], episodes)
    assert len(validated) == 0


def test_post_validation_drops_low_confidence_facts(engine, in_memory_db):
    """Facts with confidence < 0.7 are dropped."""
    fact = ExtractedFact(
        statement="A fact.",
        confidence=0.5,  # below 0.7 threshold
        evidence_episode_ids=["ep-0", "ep-1"],
    )
    episodes = [_ep("0", time.time(), "content0"), _ep("1", time.time(), "content1")]
    validated = engine._post_validate_semantic([fact], episodes)
    assert len(validated) == 0


def test_post_validation_drops_single_episode_patterns(engine, in_memory_db):
    """Patterns with evidence from only 1 episode are dropped."""
    pattern = ExtractedPattern(
        description="A pattern.",
        confidence=0.8,
        evidence_episode_ids=["ep-0"],  # only 1
    )
    episodes = [_ep("0", time.time(), "content")]
    validated = engine._post_validate_procedural([pattern], episodes)
    assert len(validated) == 0


def test_post_validation_drops_low_confidence_patterns(engine, in_memory_db):
    """Patterns with confidence < 0.6 are dropped."""
    pattern = ExtractedPattern(
        description="A pattern.",
        confidence=0.4,  # below 0.6 threshold
        evidence_episode_ids=["ep-0", "ep-1"],
    )
    episodes = [_ep("0", time.time(), "content0"), _ep("1", time.time(), "content1")]
    validated = engine._post_validate_procedural([pattern], episodes)
    assert len(validated) == 0


# ---------------------------------------------------------------------------
# Tests: Text similarity fallback
# ---------------------------------------------------------------------------

def test_text_similarity_returns_high_for_identical(engine):
    sim = ConsolidationEngine._text_similarity("hello world", "hello world")
    assert sim == 1.0


def test_text_similarity_returns_zero_for_disjoint(engine):
    sim = ConsolidationEngine._text_similarity("hello", "goodbye")
    assert sim == 0.0


def test_text_similarity_returns_partial(engine):
    sim = ConsolidationEngine._text_similarity("hello world", "hello there")
    assert 0.0 < sim < 1.0


# ---------------------------------------------------------------------------
# Tests: Consolidation weight bumping
# ---------------------------------------------------------------------------

def test_bump_consolidation_weights(engine, in_memory_db):
    """Consolidation weights are bumped for contributing episodes."""
    now = time.time()
    ep_ids = [str(uuid.uuid4()) for _ in range(3)]
    for ep_id in ep_ids:
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived, consolidation_weight) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ep_id, "episodic", "content", "hash", 0.5, 1.0, now, 0, 0.0),
        )

    asyncio.run(engine._bump_consolidation_weights(ep_ids))

    rows = in_memory_db.execute(
        "SELECT id, consolidation_weight FROM memories WHERE id IN (" + ",".join("?" * len(ep_ids)) + ")",
        ep_ids,
    ).fetchall()
    for row in rows:
        assert row["consolidation_weight"] == DEFAULT_CONSOLIDATION_WEIGHT_BUMP


# ---------------------------------------------------------------------------
# Tests: Semantic storage with reinforcement
# ---------------------------------------------------------------------------

def test_store_semantic_facts_deduplicates_by_similarity(engine, in_memory_db):
    """When a fact with similar statement exists, it is reinforced instead of creating a duplicate.

    Note: text-similarity fallback (Jaccard) has lower recall than ChromaDB embeddings.
    This test uses identical statements to guarantee match with the fallback.
    """
    from sentient.memory.semantic import SemanticFact

    now = time.time()
    existing_fact = SemanticFact(
        fact_id=str(uuid.uuid4()),
        statement="Creator prefers Python for scripts.",
        confidence=0.8,
        evidence_episode_ids=["ep-old"],
        evidence_count=1,
        first_observed=now - 1000,
        last_reinforced=now - 1000,
        reinforcement_count=1,
    )
    asyncio.run(engine.memory.semantic_store.store(existing_fact))

    # New fact with identical statement — should be detected as duplicate via Jaccard=1.0
    new_fact = SemanticFact(
        fact_id=str(uuid.uuid4()),
        statement="Creator prefers Python for scripts.",
        confidence=0.85,
        evidence_episode_ids=["ep-0", "ep-1"],
        evidence_count=2,
        first_observed=now,
        last_reinforced=now,
        reinforcement_count=1,
    )

    asyncio.run(engine._store_semantic_facts([new_fact], [_ep("0", now, "c0"), _ep("1", now, "c1")]))

    # Check that only one fact remains (reinforced, not duplicated)
    all_facts = asyncio.run(engine.memory.semantic_store.list_all())
    assert len(all_facts) == 1
    assert all_facts[0]["reinforcement_count"] == 2


# ---------------------------------------------------------------------------
# Tests: Consolidation cycle idempotency
# ---------------------------------------------------------------------------

def test_consolidate_cycle_idempotent(engine, mock_gateway, in_memory_db):
    """Calling consolidate_cycle twice in succession — second call is skipped."""
    now = time.time()
    for i in range(7):
        in_memory_db.execute(
            "INSERT INTO memories (id, memory_type, content, content_hash, importance, confidence, created_at, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ep-{i}", "episodic", f"content {i}", f"hash{i}", 0.5, 1.0, now - 100 + i, 0),
        )

    semantic_response = AsyncMock()
    semantic_response.error = None
    semantic_response.text = SemanticFactList(facts=[]).model_dump_json()

    procedural_response = AsyncMock()
    procedural_response.error = None
    procedural_response.text = ProceduralPatternList(patterns=[]).model_dump_json()

    mock_gateway.infer = AsyncMock(side_effect=[semantic_response, procedural_response])

    # First call — runs consolidation and writes to consolidation_log
    result1 = asyncio.run(engine.consolidate_cycle())
    assert result1["status"] == "completed"
    assert result1["episodes_processed"] == 7

    # Second call — no new episodes since last consolidation
    result2 = asyncio.run(engine.consolidate_cycle())
    assert result2["status"] == "skipped"
    assert result2["reason"] == "insufficient_episodes"
