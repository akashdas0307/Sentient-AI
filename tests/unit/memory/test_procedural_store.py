"""Unit tests for ProceduralStore."""
from __future__ import annotations

import sqlite3
import time

import pytest

from sentient.memory.architecture import MemoryArchitecture
from sentient.memory.procedural import ProceduralPattern, ProceduralStore


class TestProceduralPatternModel:
    def test_create_minimal_pattern(self) -> None:
        pattern = ProceduralPattern(
            pattern_id="test-id",
            description="How to debug Python",
            first_observed=time.time(),
            last_reinforced=time.time(),
        )
        assert pattern.pattern_id == "test-id"
        assert pattern.confidence == 0.5
        assert pattern.reinforcement_count == 1
        assert pattern.trigger_context == ""

    def test_create_full_pattern(self) -> None:
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="test-id-2",
            description="Akash prefers async workflows",
            trigger_context="when planning a new task",
            confidence=0.8,
            evidence_episode_ids=["ep1", "ep2", "ep3"],
            evidence_count=3,
            first_observed=now,
            last_reinforced=now,
            reinforcement_count=5,
        )
        assert pattern.confidence == 0.8
        assert pattern.evidence_count == 3
        assert pattern.reinforcement_count == 5
        assert pattern.trigger_context == "when planning a new task"


class TestProceduralStore:
    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.Connection(":memory:", isolation_level=None)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()

    @pytest.fixture
    def store(self, conn: sqlite3.Connection) -> ProceduralStore:
        return ProceduralStore(conn)

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, store: ProceduralStore) -> None:
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="pattern-1",
            description="Akash prefers concise code reviews",
            trigger_context="code review context",
            confidence=0.7,
            evidence_episode_ids=["ep1", "ep2"],
            evidence_count=2,
            first_observed=now,
            last_reinforced=now,
        )
        stored_id = await store.store(pattern)
        assert stored_id == "pattern-1"

        results = await store.retrieve("code review", k=3)
        assert len(results) == 1
        assert results[0]["description"] == "Akash prefers concise code reviews"

    @pytest.mark.asyncio
    async def test_store_and_retrieve_no_query(self, store: ProceduralStore) -> None:
        now = time.time()
        for i in range(3):
            pattern = ProceduralPattern(
                pattern_id=f"pattern-{i}",
                description=f"Pattern {i}",
                first_observed=now,
                last_reinforced=now,
            )
            await store.store(pattern)

        results = await store.retrieve("", k=2)
        assert len(results) == 2
        assert results[0]["confidence"] >= results[1]["confidence"]

    @pytest.mark.asyncio
    async def test_reinforce(self, store: ProceduralStore) -> None:
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="pattern-reinforce",
            description="Test pattern",
            confidence=0.5,
            first_observed=now,
            last_reinforced=now,
            reinforcement_count=1,
        )
        await store.store(pattern)

        await store.reinforce("pattern-reinforce")
        results = await store.retrieve("Test", k=1)
        assert len(results) == 1
        assert results[0]["reinforcement_count"] == 2
        assert results[0]["confidence"] == 0.55  # 0.5 + 0.05

    @pytest.mark.asyncio
    async def test_reinforce_caps_at_one(self, store: ProceduralStore) -> None:
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="pattern-max",
            description="Maxed pattern",
            confidence=0.96,
            first_observed=now,
            last_reinforced=now,
        )
        await store.store(pattern)
        await store.reinforce("pattern-max")
        results = await store.retrieve("Maxed", k=1)
        assert results[0]["confidence"] == 1.0  # capped

    @pytest.mark.asyncio
    async def test_list_all(self, store: ProceduralStore) -> None:
        now = time.time()
        for i in range(5):
            pattern = ProceduralPattern(
                pattern_id=f"list-pattern-{i}",
                description=f"Listable pattern {i}",
                first_observed=now,
                last_reinforced=now,
            )
            await store.store(pattern)

        all_patterns = await store.list_all()
        assert len(all_patterns) == 5
        for i in range(len(all_patterns) - 1):
            assert all_patterns[i]["confidence"] >= all_patterns[i + 1]["confidence"]

    @pytest.mark.asyncio
    async def test_evidence_ids_deserialized(self, store: ProceduralStore) -> None:
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="evidence-test",
            description="Multi-evidence pattern",
            evidence_episode_ids=["ep-a", "ep-b", "ep-c"],
            evidence_count=3,
            first_observed=now,
            last_reinforced=now,
        )
        await store.store(pattern)
        results = await store.retrieve("Multi-evidence")
        assert len(results) == 1
        assert results[0]["evidence_episode_ids"] == ["ep-a", "ep-b", "ep-c"]

    @pytest.mark.asyncio
    async def test_idempotent_table_creation(self, conn: sqlite3.Connection) -> None:
        store1 = ProceduralStore(conn)
        store2 = ProceduralStore(conn)
        assert store1 is not None
        assert store2 is not None


class TestProceduralStoreViaArchitecture:
    @pytest.fixture
    def arch(self) -> MemoryArchitecture:
        arch = MemoryArchitecture(
            config={"storage": {"sqlite_path": ":memory:"}}
        )
        return arch

    @pytest.mark.asyncio
    async def test_idempotent_initialize(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        await arch.initialize()

    @pytest.mark.asyncio
    async def test_retrieve_procedural_empty(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        results = await arch.retrieve_procedural("anything", k=3)
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_procedural_with_data(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        now = time.time()
        pattern = ProceduralPattern(
            pattern_id="arch-pattern-1",
            description="Architecture test pattern",
            trigger_context="testing context",
            confidence=0.8,
            evidence_episode_ids=["ep1", "ep2"],
            evidence_count=2,
            first_observed=now,
            last_reinforced=now,
        )
        await arch.procedural_store.store(pattern)

        results = await arch.retrieve_procedural("Architecture", k=3)
        assert len(results) == 1
        assert results[0]["description"] == "Architecture test pattern"
