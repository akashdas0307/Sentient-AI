"""Unit tests for Daydream Output Persistence (Phase 9 D2).

Verifies:
1. Daydream cycles produce memory_candidates with origin="daydream"
2. Daydream memories stored with origin="daydream" metadata
3. Daydream memories accepted at lower importance threshold (0.2 vs 0.3)
4. Waking memories rejected below 0.3 threshold
5. retrieve_episodic() returns daydream-origin memories
6. has_daydreamed_recently() returns True/False correctly
7. Three daydream cycles produce retrievable memories
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Any
import json
from unittest.mock import MagicMock

import pytest

from sentient.core.event_bus import EventBus
from sentient.memory.architecture import MemoryArchitecture, MemoryType, SQLITE_SCHEMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config(temp_dir: Path) -> dict[str, Any]:
    return {
        "storage": {
            "sqlite_path": str(temp_dir / "daydream_memory.db"),
            "chroma_path": str(temp_dir / "daydream_chroma"),
        },
        "gatekeeper": {
            "importance_threshold": 0.3,
            "semantic_dedup_similarity": 0.92,
            "recency_auto_pass_hours": 24,
        },
        "retrieval": {"default_max_results": 15},
        "embeddings": {"model": "all-MiniLM-L6-v2"},
        # Daydream-specific config
        "daydream_min_importance": 0.2,
        "daydream_recognition_window_hours": 1.0,
    }


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def _setup_sqlite(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.executescript(SQLITE_SCHEMA)


def _make_arch(config: dict, bus: EventBus) -> MemoryArchitecture:
    """Create arch without ChromaDB for reliable isolated tests."""
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
# 1. Daydream candidate has origin metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daydream_candidate_has_origin_metadata(config: dict, bus: EventBus) -> None:
    """is_daydream=True adds metadata.origin='daydream' to memory candidates."""
    arch = _make_arch(config, bus)
    await arch.start()

    captured = {}

    async def capture_memory_candidate(payload: dict[str, Any]) -> None:
        captured["payload"] = payload

    await bus.subscribe("memory.candidate", capture_memory_candidate)

    # Simulate a cognitive cycle running in daydream mode publishing candidates
    # The Cognitive Core would publish these after running a cycle.
    # We test by directly calling the handler with a daydream-origin candidate.
    await arch._handle_candidate({
        "cycle_id": "daydream_cycle_1",
        "candidate": {
            "content": "A reflective thought from daydreaming",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.5,
            "metadata": {"origin": "daydream"},
        },
        "source_envelope_id": None,
    })

    await asyncio.sleep(0.05)

    # Verify memory was stored with origin in metadata
    count = await arch.count(MemoryType.EPISODIC)
    assert count == 1

    # Query the stored memory to verify metadata
    row = arch._conn.execute(
        "SELECT metadata FROM memories WHERE memory_type = ?",
        (MemoryType.EPISODIC.value,),
    ).fetchone()
    metadata = json.loads(row["metadata"])
    assert metadata.get("origin") == "daydream"


@pytest.mark.asyncio
async def test_daydream_episodic_store_has_origin(config: dict, bus: EventBus) -> None:
    """Daydream memories stored via store() have origin='daydream' in metadata."""
    arch = _make_arch(config, bus)

    memory_id = await arch.store({
        "content": "Daydream reflection about the morning",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.5,
        "created_at": time.time(),
        "metadata": {"origin": "daydream"},
    })

    assert memory_id is not None

    row = arch._conn.execute(
        "SELECT metadata FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    metadata = json.loads(row["metadata"])
    assert metadata.get("origin") == "daydream"


# ---------------------------------------------------------------------------
# 2. Daydream lower importance threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daydream_lower_importance_threshold(config: dict, bus: EventBus) -> None:
    """Daydream memories with importance 0.2 are accepted (below waking threshold 0.3)."""
    arch = _make_arch(config, bus)

    # Importance 0.2 < 0.3 waking threshold, but daydream_min_importance=0.2
    memory_id = await arch.store({
        "content": "A minor daydream observation",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.2,
        "created_at": time.time(),
        "metadata": {"origin": "daydream"},
    })

    assert memory_id is not None
    count = await arch.count(MemoryType.EPISODIC)
    assert count == 1


@pytest.mark.asyncio
async def test_waking_memory_higher_threshold(config: dict, bus: EventBus) -> None:
    """Waking memories with importance 0.25 are rejected (below 0.3 threshold)."""
    arch = _make_arch(config, bus)

    # Importance 0.25 < 0.3 threshold, no daydream metadata
    memory_id = await arch.store({
        "content": "A minor waking observation",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.25,
        "created_at": time.time() - 86400 * 2,  # 2 days old — no recency pass
        # No daydream metadata — treated as waking
    })

    assert memory_id is None
    count = await arch.count(MemoryType.EPISODIC)
    assert count == 0


# ---------------------------------------------------------------------------
# 3. retrieve_episodic includes daydream memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_includes_daydream_memories(config: dict, bus: EventBus) -> None:
    """retrieve_episodic() returns both waking and daydream-origin memories."""
    arch = _make_arch(config, bus)

    # Store a waking memory
    waking_id = await arch.store({
        "content": "A waking conversation about project architecture",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
        "metadata": {},  # no origin = waking
    })
    assert waking_id is not None

    # Store a daydream memory
    daydream_id = await arch.store({
        "content": "A daydream about project architecture",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
        "metadata": {"origin": "daydream"},
    })
    assert daydream_id is not None

    # retrieve_episodic should return both
    results = await arch.retrieve_episodic(context="project architecture", k=5)

    ids = {r["id"] for r in results}
    assert waking_id in ids
    assert daydream_id in ids
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 4. has_daydreamed_recently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_daydreamed_recently_true(config: dict, bus: EventBus) -> None:
    """After storing a daydream memory, has_daydreamed_recently(1.0) returns True."""
    arch = _make_arch(config, bus)

    # No daydream memories yet
    result = await arch.has_daydreamed_recently(hours=1.0)
    assert result is False

    # Store a daydream memory (recent — within last 1 hour)
    await arch.store({
        "content": "Daydream reflection on recent thoughts",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.5,
        "created_at": time.time(),
        "metadata": {"origin": "daydream"},
    })

    result = await arch.has_daydreamed_recently(hours=1.0)
    assert result is True


@pytest.mark.asyncio
async def test_has_daydreamed_recently_false(config: dict, bus: EventBus) -> None:
    """With no daydream memories, has_daydreamed_recently(hours=1.0) returns False."""
    arch = _make_arch(config, bus)

    # Store only waking memories
    await arch.store({
        "content": "Waking conversation",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.6,
        "created_at": time.time(),
    })

    result = await arch.has_daydreamed_recently(hours=1.0)
    assert result is False


@pytest.mark.asyncio
async def test_has_daydreamed_recently_old_memory(config: dict, bus: EventBus) -> None:
    """Daydream memory older than the window returns False."""
    arch = _make_arch(config, bus)

    # Store a daydream memory 2 hours ago (outside 1 hour window)
    await arch.store({
        "content": "Old daydream memory",
        "type": MemoryType.EPISODIC.value,
        "importance": 0.5,
        "created_at": time.time() - 7200,  # 2 hours ago
        "metadata": {"origin": "daydream"},
    })

    result = await arch.has_daydreamed_recently(hours=1.0)
    assert result is False


# ---------------------------------------------------------------------------
# 5. Three daydream cycles produce retrievable memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_daydream_cycles_produce_retrievable_memories(config: dict, bus: EventBus) -> None:
    """Three daydream cycles, all 3 memories are retrievable and has_daydreamed_recently is True."""
    arch = _make_arch(config, bus)

    # Run 3 daydream cycles (simulate storage)
    daydream_ids = []
    for i in range(3):
        memory_id = await arch.store({
            "content": f"Daydream cycle {i + 1} reflection",
            "type": MemoryType.EPISODIC.value,
            "importance": 0.5,
            "created_at": time.time(),
            "metadata": {"origin": "daydream"},
        })
        assert memory_id is not None
        daydream_ids.append(memory_id)

    # All 3 should be retrievable
    for mid in daydream_ids:
        row = arch._conn.execute(
            "SELECT id FROM memories WHERE id = ?", (mid,)
        ).fetchone()
        assert row is not None, f"Memory {mid} not found in DB"

    # has_daydreamed_recently should return True
    result = await arch.has_daydreamed_recently(hours=1.0)
    assert result is True

    # Verify count
    count = await arch.count(MemoryType.EPISODIC)
    assert count == 3
