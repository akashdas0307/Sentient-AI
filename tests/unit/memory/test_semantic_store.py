"""Unit tests for SemanticStore."""
from __future__ import annotations

import sqlite3
import time

import pytest

from sentient.memory.architecture import MemoryArchitecture
from sentient.memory.semantic import SemanticFact, SemanticStore


class TestSemanticFactModel:
    def test_create_minimal_fact(self) -> None:
        fact = SemanticFact(
            fact_id="test-id",
            statement="The sky is blue",
            first_observed=time.time(),
            last_reinforced=time.time(),
        )
        assert fact.fact_id == "test-id"
        assert fact.confidence == 0.5
        assert fact.reinforcement_count == 1
        assert fact.evidence_episode_ids == []

    def test_create_full_fact(self) -> None:
        now = time.time()
        fact = SemanticFact(
            fact_id="test-id-2",
            statement="Water freezes at 0°C",
            confidence=0.8,
            evidence_episode_ids=["ep1", "ep2", "ep3"],
            evidence_count=3,
            first_observed=now,
            last_reinforced=now,
            reinforcement_count=5,
        )
        assert fact.confidence == 0.8
        assert fact.evidence_count == 3
        assert fact.reinforcement_count == 5
        assert len(fact.evidence_episode_ids) == 3


class TestSemanticStore:
    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.Connection(":memory:", isolation_level=None)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()

    @pytest.fixture
    def store(self, conn: sqlite3.Connection) -> SemanticStore:
        return SemanticStore(conn)

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, store: SemanticStore) -> None:
        now = time.time()
        fact = SemanticFact(
            fact_id="fact-1",
            statement="Akash prefers Python",
            confidence=0.7,
            evidence_episode_ids=["ep1", "ep2"],
            evidence_count=2,
            first_observed=now,
            last_reinforced=now,
        )
        stored_id = await store.store(fact)
        assert stored_id == "fact-1"

        results = await store.retrieve("Akash", k=3)
        assert len(results) == 1
        assert results[0]["statement"] == "Akash prefers Python"

    @pytest.mark.asyncio
    async def test_store_and_retrieve_no_query(self, store: SemanticStore) -> None:
        now = time.time()
        for i in range(3):
            fact = SemanticFact(
                fact_id=f"fact-{i}",
                statement=f"Fact {i}",
                first_observed=now,
                last_reinforced=now,
            )
            await store.store(fact)

        results = await store.retrieve("", k=2)
        assert len(results) == 2
        # Ordered by confidence desc
        assert results[0]["confidence"] >= results[1]["confidence"]

    @pytest.mark.asyncio
    async def test_reinforce(self, store: SemanticStore) -> None:
        now = time.time()
        fact = SemanticFact(
            fact_id="fact-reinforce",
            statement="Test fact",
            confidence=0.5,
            first_observed=now,
            last_reinforced=now,
            reinforcement_count=1,
        )
        await store.store(fact)

        await store.reinforce("fact-reinforce")
        results = await store.retrieve("Test", k=1)
        assert len(results) == 1
        assert results[0]["reinforcement_count"] == 2
        assert results[0]["confidence"] == 0.55  # 0.5 + 0.05

    @pytest.mark.asyncio
    async def test_reinforce_caps_at_one(self, store: SemanticStore) -> None:
        now = time.time()
        fact = SemanticFact(
            fact_id="fact-max",
            statement="Maxed fact",
            confidence=0.96,
            first_observed=now,
            last_reinforced=now,
        )
        await store.store(fact)
        await store.reinforce("fact-max")
        results = await store.retrieve("Maxed", k=1)
        assert results[0]["confidence"] == 1.0  # capped

    @pytest.mark.asyncio
    async def test_list_all(self, store: SemanticStore) -> None:
        now = time.time()
        for i in range(5):
            fact = SemanticFact(
                fact_id=f"list-fact-{i}",
                statement=f"Listable fact {i}",
                first_observed=now,
                last_reinforced=now,
            )
            await store.store(fact)

        all_facts = await store.list_all()
        assert len(all_facts) == 5
        # Ordered by confidence desc
        for i in range(len(all_facts) - 1):
            assert all_facts[i]["confidence"] >= all_facts[i + 1]["confidence"]

    @pytest.mark.asyncio
    async def test_evidence_ids_deserialized(self, store: SemanticStore) -> None:
        now = time.time()
        fact = SemanticFact(
            fact_id="evidence-test",
            statement="Multi-evidence fact",
            evidence_episode_ids=["ep-a", "ep-b", "ep-c"],
            evidence_count=3,
            first_observed=now,
            last_reinforced=now,
        )
        await store.store(fact)
        results = await store.retrieve("Multi-evidence")
        assert len(results) == 1
        assert results[0]["evidence_episode_ids"] == ["ep-a", "ep-b", "ep-c"]

    @pytest.mark.asyncio
    async def test_idempotent_table_creation(self, conn: sqlite3.Connection) -> None:
        # Should not raise on second initialization
        store1 = SemanticStore(conn)
        store2 = SemanticStore(conn)
        assert store1 is not None
        assert store2 is not None


class TestSemanticStoreViaArchitecture:
    @pytest.fixture
    def arch(self) -> MemoryArchitecture:
        arch = MemoryArchitecture(
            config={"storage": {"sqlite_path": ":memory:"}}
        )
        return arch

    @pytest.mark.asyncio
    async def test_idempotent_initialize(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        await arch.initialize()  # Should not raise

    @pytest.mark.asyncio
    async def test_retrieve_semantic_empty(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        results = await arch.retrieve_semantic("anything", k=3)
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_semantic_with_data(self, arch: MemoryArchitecture) -> None:
        await arch.initialize()
        now = time.time()
        fact = SemanticFact(
            fact_id="arch-fact-1",
            statement="Architecture test fact",
            confidence=0.8,
            evidence_episode_ids=["ep1", "ep2"],
            evidence_count=2,
            first_observed=now,
            last_reinforced=now,
        )
        await arch.semantic_store.store(fact)

        results = await arch.retrieve_semantic("Architecture", k=3)
        assert len(results) == 1
        assert results[0]["statement"] == "Architecture test fact"
