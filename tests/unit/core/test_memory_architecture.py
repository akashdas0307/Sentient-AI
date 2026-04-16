"""Unit tests for src/sentient/memory/architecture.py.

Covers MemoryArchitecture initialization, store/retrieve CRUD, gatekeeper
integration, multi-path retrieval, FTS5 round-trip, lifecycle transitions,
and error paths.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.core.event_bus import EventBus
from sentient.memory.architecture import MemoryArchitecture, MemoryType, SQLITE_SCHEMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a real temporary directory for SQLite/Chroma files."""
    return tmp_path


@pytest.fixture
def config(temp_dir: Path) -> dict[str, Any]:
    """Config using a temp SQLite file (file-based for reliable isolation)."""
    return {
        "storage": {
            "sqlite_path": str(temp_dir / "memory.db"),
            "chroma_path": str(temp_dir / "chroma"),
        },
        "gatekeeper": {
            "importance_threshold": 0.3,
            "semantic_dedup_similarity": 0.92,
            "recency_auto_pass_hours": 24,
        },
        "retrieval": {"default_max_results": 15},
        "embeddings": {"model": "all-MiniLM-L6-v2"},
    }


@pytest.fixture
def bus() -> EventBus:
    """Fresh EventBus instance for each test."""
    return EventBus()


def _setup_sqlite(conn: sqlite3.Connection) -> None:
    """Set up the SQLite schema on an existing connection."""
    conn.row_factory = sqlite3.Row
    conn.executescript(SQLITE_SCHEMA)


@pytest.fixture
async def arch(config: dict, bus: EventBus) -> MemoryArchitecture:
    """Initialized MemoryArchitecture with mocked ChromaDB/embedder."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = MagicMock()
    arch._embedder = MagicMock()
    arch._chroma_client = MagicMock()
    arch._conn = sqlite3.connect(
        str(Path(config["storage"]["sqlite_path"])),
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()
    yield arch
    await arch.shutdown()


@pytest.fixture
async def arch_no_chroma(config: dict, bus: EventBus) -> MemoryArchitecture:
    """MemoryArchitecture without ChromaDB or embedder."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = None
    arch._embedder = None
    arch._conn = sqlite3.connect(
        str(Path(config["storage"]["sqlite_path"])),
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()
    yield arch
    await arch.shutdown()


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Mock embedder that encodes text to a fixed vector."""
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=MagicMock(tolist=lambda: [0.1] * 384))
    return embedder


# ---------------------------------------------------------------------------
# Helper to make arch with schema for tests that need their own instance
# ---------------------------------------------------------------------------


def _make_arch(config: dict, bus: EventBus) -> MemoryArchitecture:
    """Create arch with schema but no ChromaDB for simpler tests."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = None
    arch._embedder = None
    arch._conn = sqlite3.connect(
        str(Path(config["storage"]["sqlite_path"])),
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()
    return arch


# ---------------------------------------------------------------------------
# 1. CRUD for each memory type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_episodic(arch: MemoryArchitecture) -> None:
    """Store and retrieve an episodic memory, verify fields."""
    candidate = {
        "content": "Had coffee with Sarah this morning",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "confidence": 0.9,
        "entity_tags": ["Sarah"],
        "topic_tags": ["coffee"],
        "created_at": time.time(),
    }
    memory_id = await arch.store(candidate)
    assert memory_id is not None

    results = await arch.retrieve(query="coffee")
    assert len(results) == 1
    m = results[0]
    assert m["memory_type"] == MemoryType.EPISODIC.value
    assert m["content"] == candidate["content"]
    assert m["entity_tags"] == ["Sarah"]
    assert m["topic_tags"] == ["coffee"]
    assert m["importance"] == 0.6


@pytest.mark.asyncio
async def test_crud_semantic(arch: MemoryArchitecture) -> None:
    """Store and retrieve a semantic memory."""
    candidate = {
        "content": "Water freezes at 0 degrees Celsius",
        "type": MemoryType.SEMANTIC.value,
        "importance": 0.7,
        "confidence": 1.0,
        "entity_tags": [],
        "topic_tags": ["science", "physics"],
        "created_at": time.time(),
    }
    memory_id = await arch.store(candidate)
    assert memory_id is not None

    results = await arch.retrieve(query="water freezes")
    assert len(results) == 1
    assert results[0]["memory_type"] == MemoryType.SEMANTIC.value
    assert results[0]["confidence"] == 1.0


@pytest.mark.asyncio
async def test_crud_procedural(arch: MemoryArchitecture) -> None:
    """Store and retrieve a procedural memory."""
    candidate = {
        "content": "How to brew pour-over coffee: 20g coffee to 300ml water",
        "type": MemoryType.PROCEDURAL.value,
        "importance": 0.5,
        "confidence": 0.95,
        "entity_tags": [],
        "topic_tags": ["coffee", "brewing"],
        "created_at": time.time(),
    }
    memory_id = await arch.store(candidate)
    assert memory_id is not None

    results = await arch.retrieve(query="pour-over")
    assert len(results) == 1
    assert results[0]["memory_type"] == MemoryType.PROCEDURAL.value


@pytest.mark.asyncio
async def test_crud_emotional(arch: MemoryArchitecture) -> None:
    """Store and retrieve an emotional memory."""
    candidate = {
        "content": "Felt a deep sense of joy watching the sunrise",
        "type": MemoryType.EMOTIONAL.value,
        "importance": 0.8,
        "confidence": 0.85,
        "entity_tags": [],
        "topic_tags": ["sunrise", "nature"],
        "emotional_tags": {"joy": 0.9, "peace": 0.7},
        "created_at": time.time(),
    }
    memory_id = await arch.store(candidate)
    assert memory_id is not None

    results = await arch.retrieve(query="sunrise")
    assert len(results) == 1
    assert results[0]["memory_type"] == MemoryType.EMOTIONAL.value
    assert results[0]["emotional_tags"]["joy"] == 0.9


# ---------------------------------------------------------------------------
# 2. Gatekeeper integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gatekeeper_skip_low_importance(config: dict, bus: EventBus) -> None:
    """Gatekeeper returns skip when importance is below threshold."""
    arch = _make_arch(config, bus)

    # Importance below threshold 0.3 should result in skip
    candidate = {
        "content": "Minor detail not worth remembering",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.1,  # below 0.3 threshold
        "created_at": time.time() - 3600 * 48,  # not recent enough to auto-pass
    }

    result = await arch.store(candidate)
    assert result is None  # skipped


@pytest.mark.asyncio
async def test_gatekeeper_reinforce_exact_match(config: dict, bus: EventBus) -> None:
    """Exact content match triggers reinforce action."""
    arch = _make_arch(config, bus)

    content = "This is a memory I want to reinforce"

    # First store
    memory_id1 = await arch.store({
        "content": content,
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })
    assert memory_id1 is not None

    # Read reinforcement_count before
    row_before = arch._conn.execute(
        "SELECT reinforcement_count FROM memories WHERE id = ?", (memory_id1,)
    ).fetchone()
    count_before = row_before["reinforcement_count"]

    # Store exact same content — should reinforce
    result = await arch.store({
        "content": content,
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    # Reinforce returns the same memory_id
    assert result == memory_id1

    # Check reinforcement_count incremented
    row_after = arch._conn.execute(
        "SELECT reinforcement_count FROM memories WHERE id = ?", (memory_id1,)
    ).fetchone()
    assert row_after["reinforcement_count"] == count_before + 1


@pytest.mark.asyncio
async def test_gatekeeper_update_semantic_match(
    config: dict, bus: EventBus, mock_embedder: MagicMock,
) -> None:
    """High semantic similarity triggers update action."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = MagicMock()
    arch._embedder = mock_embedder
    arch._conn = sqlite3.connect(
        ":memory:",
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()

    # Simulate semantic search returning a similar memory
    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [["existing-memory-id"]],
        "distances": [[0.05]],  # high similarity (1 - 0.05 = 0.95)
        "documents": [["I like coffee in the morning"]],
    })

    # Patch _reinforce to track that it was called
    arch._reinforce = AsyncMock()

    candidate = {
        "content": "I enjoy drinking coffee each day",
        "type": MemoryType.SEMANTIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    }
    result = await arch.store(candidate)

    # Should return the existing memory id (update action)
    assert result == "existing-memory-id"
    arch._reinforce.assert_awaited_once_with("existing-memory-id")


@pytest.mark.asyncio
async def test_gatekeeper_flag_contradiction(
    config: dict, bus: EventBus, mock_embedder: MagicMock,
) -> None:
    """Possible contradiction is flagged and new memory still stored."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = MagicMock()
    arch._embedder = mock_embedder
    arch._conn = sqlite3.connect(
        ":memory:",
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()

    # Semantic search returns a memory with negation difference
    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [["existing-memory-id"]],
        "distances": [[0.35]],  # similarity 0.65 — in contradiction range
        "documents": [["I do not like coffee"]],
    })

    candidate = {
        "content": "I like coffee",  # negation differs
        "type": MemoryType.SEMANTIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    }
    result = await arch.store(candidate)

    # Should still store (contradiction is logged for sleep resolution)
    assert result is not None

    # Check contradiction was recorded
    rows = arch._conn.execute("SELECT * FROM contradictions").fetchall()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_gatekeeper_store_passes_all_filters(arch: MemoryArchitecture) -> None:
    """New memory with no dedup/contradiction passes gatekeeper and is stored."""
    arch._chroma_collection = MagicMock()
    arch._embedder = MagicMock()
    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [[]],
        "distances": [[]],
        "documents": [[]],
    })

    candidate = {
        "content": "A brand new unique experience",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    }
    result = await arch.store(candidate)

    assert result is not None
    count = await arch.count(MemoryType.EPISODIC)
    assert count == 1


# ---------------------------------------------------------------------------
# 3. Multi-path retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_tag_based_via_fts(arch_no_chroma: MemoryArchitecture) -> None:
    """Tag-based retrieval uses SQLite FTS5."""
    arch = arch_no_chroma

    await arch.store({
        "content": "Meeting with John about the project",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "entity_tags": ["John"],
        "topic_tags": ["project"],
        "created_at": time.time(),
    })
    await arch.store({
        "content": "Lunch with Sarah",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.5,
        "entity_tags": ["Sarah"],
        "topic_tags": ["food"],
        "created_at": time.time(),
    })

    results = await arch.retrieve(tags=["John"])
    assert len(results) == 1
    assert "John" in results[0]["content"]


@pytest.mark.asyncio
async def test_retrieve_semantic_via_chroma(
    arch: MemoryArchitecture, mock_embedder: MagicMock,
) -> None:
    """Semantic retrieval uses ChromaDB when FTS misses."""
    arch._embedder = mock_embedder

    # Pre-insert a memory that ChromaDB will find
    arch._conn.execute(
        """
        INSERT INTO memories (id, memory_type, content, content_hash, importance,
            confidence, created_at, entity_tags, topic_tags, emotional_tags, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "chroma-memory-id",
            MemoryType.SEMANTIC.value,
            "A semantic memory about coffee preferences",
            "hash123",
            0.7,
            1.0,
            time.time(),
            "[]",
            "[]",
            "{}",
            "{}",
        ),
    )

    # Chroma returns a memory not in FTS index (no matching tags)
    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [["chroma-memory-id"]],
        "distances": [[0.1]],
        "documents": [["A semantic memory about coffee preferences"]],
    })

    results = await arch.retrieve(query="coffee preferences")

    assert len(results) == 1
    assert results[0]["retrieval_path"] == "semantic"
    assert results[0]["id"] == "chroma-memory-id"


@pytest.mark.asyncio
async def test_retrieve_combined_results_from_both_paths(
    config: dict, bus: EventBus, mock_embedder: MagicMock,
) -> None:
    """Memory found by both FTS and ChromaDB gets retrieval_path='both'."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._embedder = mock_embedder
    arch._chroma_collection = MagicMock()
    arch._conn = sqlite3.connect(
        ":memory:",
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()

    # Pre-insert memory with tags so FTS will find it
    arch._conn.execute(
        """
        INSERT INTO memories (id, memory_type, content, content_hash, importance,
            confidence, created_at, entity_tags, topic_tags, emotional_tags, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "shared-memory-id",
            MemoryType.EPISODIC.value,
            "Meeting notes about the quarterly review",
            "hash456",
            0.7,
            1.0,
            time.time(),
            "[]",
            '["quarterly"]',  # JSON array so FTS matches "quarterly"
            "{}",
            "{}",
        ),
    )
    # Also insert into FTS
    arch._conn.execute(
        "INSERT INTO memories_fts (id, content, entity_tags, topic_tags) VALUES (?, ?, ?, ?)",
        ("shared-memory-id", "Meeting notes about the quarterly review", "", "quarterly"),
    )

    # ChromaDB also finds the same memory
    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [["shared-memory-id"]],
        "distances": [[0.1]],  # high similarity
        "documents": [["Meeting notes about the quarterly review"]],
    })

    results = await arch.retrieve(query="quarterly")

    assert len(results) == 1
    assert results[0]["retrieval_path"] == "both"


# ---------------------------------------------------------------------------
# 4. FTS5 full-text search round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fts5_search_by_keyword(arch_no_chroma: MemoryArchitecture) -> None:
    """Store multiple memories, search by keyword returns correct results."""
    arch = arch_no_chroma

    memories = [
        {"content": "Python is a programming language", "topic_tags": ["coding"]},
        {"content": "JavaScript is also a programming language", "topic_tags": ["coding"]},
        {"content": "Paris is the capital of France", "topic_tags": ["geography"]},
    ]
    for m in memories:
        await arch.store({
            **m,
            "type": MemoryType.SEMANTIC.value,
            "importance": 0.6,
            "created_at": time.time(),
        })

    results = await arch.retrieve(query="programming")
    assert len(results) == 2
    contents = [r["content"] for r in results]
    assert "Python is a programming language" in contents
    assert "JavaScript is also a programming language" in contents


@pytest.mark.asyncio
async def test_fts5_search_no_results(arch_no_chroma: MemoryArchitecture) -> None:
    """FTS search with no matches returns empty list."""
    arch = arch_no_chroma

    await arch.store({
        "content": "A memory about cooking pasta",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.5,
        "created_at": time.time(),
    })

    results = await arch.retrieve(query="astronomy")
    assert len(results) == 0


# ---------------------------------------------------------------------------
# 5. Memory lifecycle state transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reinforce_increments_reinforcement_count(config: dict, bus: EventBus) -> None:
    """Storing exact duplicate increments reinforcement_count."""
    arch = _make_arch(config, bus)

    content = "Reinforceable memory"

    # First store
    await arch.store({
        "content": content,
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    # Store identical again
    await arch.store({
        "content": content,
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    # Store identical a third time
    await arch.store({
        "content": content,
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    row = arch._conn.execute(
        "SELECT reinforcement_count FROM memories"
    ).fetchone()
    # reinforcement_count starts at 1, increments on each reinforce
    assert row["reinforcement_count"] == 3


@pytest.mark.asyncio
async def test_retrieve_increments_access_count(arch: MemoryArchitecture) -> None:
    """Retrieving a memory increments its access_count."""
    arch._chroma_collection = None
    arch._embedder = None

    memory_id = await arch.store({
        "content": "A memory to retrieve multiple times",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    # Check access_count before
    row_before = arch._conn.execute(
        "SELECT access_count FROM memories WHERE id = ?", (memory_id,)
    ).fetchone()
    assert row_before["access_count"] == 0

    # Retrieve it
    await arch.retrieve(query="retrieve multiple times")

    row_after = arch._conn.execute(
        "SELECT access_count FROM memories WHERE id = ?", (memory_id,)
    ).fetchone()
    assert row_after["access_count"] == 1


# ---------------------------------------------------------------------------
# 6. Error / edge case paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_low_importance_returns_none(config: dict, bus: EventBus) -> None:
    """Low-importance candidate below threshold returns None from store."""
    arch = _make_arch(config, bus)

    result = await arch.store({
        "content": "trivial observation",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.1,  # below threshold of 0.3
        "created_at": time.time() - 86400 * 7,  # 7 days old (no recency pass)
    })
    assert result is None


@pytest.mark.asyncio
async def test_store_no_chroma_no_embedder(config: dict, bus: EventBus) -> None:
    """Store works even when ChromaDB and embedder are unavailable."""
    arch = _make_arch(config, bus)

    result = await arch.store({
        "content": "Memory without semantic indexing",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    assert result is not None
    count = await arch.count()
    assert count == 1


@pytest.mark.asyncio
async def test_retrieve_with_missing_chroma_collection(
    arch_no_chroma: MemoryArchitecture,
) -> None:
    """Retrieval works when ChromaDB collection is not available."""
    arch = arch_no_chroma

    await arch.store({
        "content": "Memory without ChromaDB",
        "type": MemoryType.SEMANTIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    results = await arch.retrieve(query="ChromaDB")
    # FTS still works
    assert len(results) == 1


@pytest.mark.asyncio
async def test_count_memory_type(arch: MemoryArchitecture) -> None:
    """count() returns correct count per memory type."""
    arch._chroma_collection = None
    arch._embedder = None

    for i in range(3):
        await arch.store({
            "content": f"Episodic memory number {i}",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.6,
            "created_at": time.time(),
        })
    for i in range(2):
        await arch.store({
            "content": f"Semantic memory number {i}",
            "type": MemoryType.SEMANTIC.value,
            "importance": 0.6,
            "created_at": time.time(),
        })

    assert await arch.count(MemoryType.EPISODIC) == 3
    assert await arch.count(MemoryType.SEMANTIC) == 2
    assert await arch.count() == 5


@pytest.mark.asyncio
async def test_count_no_memories(arch: MemoryArchitecture) -> None:
    """count() returns 0 when no memories stored."""
    arch._chroma_collection = None
    arch._embedder = None
    assert await arch.count() == 0
    assert await arch.count(MemoryType.EPISODIC) == 0


# ---------------------------------------------------------------------------
# 7. Event bus integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_publishes_memory_stored_event(config: dict, bus: EventBus) -> None:
    """store() publishes 'memory.stored' event on the event bus."""
    arch = _make_arch(config, bus)

    handler = AsyncMock()
    await bus.subscribe("memory.stored", handler)

    await arch.store({
        "content": "Memory that triggers event",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    await asyncio.sleep(0.05)
    handler.assert_awaited_once()
    call_args = handler.call_args[0][0]
    assert call_args["event_type"] == "memory.stored"
    assert "memory_id" in call_args


# ---------------------------------------------------------------------------
# 8. Health pulse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_pulse_returns_counts(arch: MemoryArchitecture) -> None:
    """health_pulse() returns correct memory counts and module status."""
    # Keep mocked chroma_collection so chroma_available is True
    arch._embedder = None

    for i in range(2):
        await arch.store({
            "content": f"Memory for health check {i}",
            "type": MemoryType.SEMANTIC.value,
            "importance": 0.6,
            "created_at": time.time(),
        })

    pulse = arch.health_pulse()
    assert pulse.metrics["total_memories"] == 2
    assert pulse.metrics["by_type"]["semantic"] == 2
    assert pulse.metrics["sqlite_available"] is True
    assert pulse.metrics["chroma_available"] is True


# ---------------------------------------------------------------------------
# 9. Lifecycle: initialize / start / shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_subscribes_to_memory_candidate(config: dict, bus: EventBus) -> None:
    """start() subscribes _handle_candidate to 'memory.candidate' events."""
    arch = _make_arch(config, bus)
    await arch.start()

    assert "memory.candidate" in bus._subscribers


@pytest.mark.asyncio
async def test_handle_candidate_stores_memory(config: dict, bus: EventBus) -> None:
    """_handle_candidate receives event and stores the candidate memory."""
    arch = _make_arch(config, bus)
    await arch.start()

    await bus.publish("memory.candidate", {
        "candidate": {
            "content": "Memory from cognitive core",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.7,
        },
        "source_envelope_id": "env-123",
        "cycle_id": "cycle-456",
    })

    await asyncio.sleep(0.05)

    count = await arch.count(MemoryType.EPISODIC)
    assert count == 1


# ---------------------------------------------------------------------------
# 10. Limit parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_respects_limit(arch: MemoryArchitecture) -> None:
    """retrieve() respects the limit parameter."""
    arch._chroma_collection = None
    arch._embedder = None

    for i in range(5):
        await arch.store({
            "content": f"Memory number {i}",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.6,
            "topic_tags": ["test"],
            "created_at": time.time(),
        })

    results = await arch.retrieve(tags=["test"], limit=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_retrieve_with_empty_query(arch: MemoryArchitecture) -> None:
    """retrieve() with no query/tags returns empty (both paths need query or tags)."""
    arch._chroma_collection = None
    arch._embedder = None

    for i in range(3):
        await arch.store({
            "content": f"Memory {i}",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.6,
            "created_at": time.time(),
        })

    # Without query or tags, both retrieval paths are skipped
    results = await arch.retrieve()
    assert len(results) == 0


# ---------------------------------------------------------------------------
# 11. Update action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_existing_increments_reinforcement(
    config: dict, bus: EventBus, mock_embedder: MagicMock,
) -> None:
    """Update action calls _reinforce on the target memory."""
    arch = MemoryArchitecture(config, event_bus=bus)
    arch._chroma_collection = MagicMock()
    arch._embedder = mock_embedder
    arch._conn = sqlite3.connect(
        ":memory:",
        isolation_level=None,
        check_same_thread=False,
    )
    _setup_sqlite(arch._conn)
    arch.set_status = MagicMock()

    arch._chroma_collection.query = MagicMock(return_value={
        "ids": [["existing-id"]],
        "distances": [[0.06]],  # similarity 0.94 — triggers update (>= 0.92)
        "documents": [["Old version of the fact"]],
    })

    arch._reinforce = AsyncMock()

    result = await arch.store({
        "content": "Updated version of the fact",
        "type": MemoryType.SEMANTIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    assert result == "existing-id"
    arch._reinforce.assert_awaited_once_with("existing-id")
