"""Phase 7 D6: Wetware test for consolidation cycle.

Wetware test for end-to-end consolidation with real Ollama LLM calls.
Integration tests (mock gateway, no real LLM) are in tests/integration/test_consolidation_cycle.py.

Run integration tests:
    pytest tests/integration/test_consolidation_cycle.py -v

Run wetware tests:
    pytest -m wetware tests/wetware/test_consolidation_cycle.py -v
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Ollama availability check
# ---------------------------------------------------------------------------

def _check_ollama_available() -> bool:
    """Return True if Ollama is running and accessible."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        return True
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _check_ollama_available(),
    reason="Ollama not running or not accessible",
)

# Mark all tests in this module as wetware (requires real LLM calls)
pytestmark = pytest.mark.wetware


# ---------------------------------------------------------------------------
# Wetware test — real Ollama LLM calls
# ---------------------------------------------------------------------------

@requires_ollama
class TestConsolidationWetware:
    """End-to-end wetware test for consolidation cycle with real Ollama LLM calls.

    Boot the full system, store episodic memories, trigger consolidation,
    and verify semantic/procedural extraction.
    """

    @pytest.fixture
    def clean_memory_data(self, tmp_path):
        """Isolated memory DB for this wetware test."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
            p = data_dir / f
            if p.exists():
                p.unlink()
        chroma_dir = data_dir / "chroma"
        if chroma_dir.exists():
            import shutil
            shutil.rmtree(chroma_dir)

        yield {
            "sqlite_path": str(data_dir / "memory.db"),
            "chroma_path": str(chroma_dir),
        }

        for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
            p = data_dir / f
            if p.exists():
                p.unlink()
        if chroma_dir.exists():
            import shutil
            shutil.rmtree(chroma_dir)

    @pytest.mark.asyncio
    async def test_full_consolidation_cycle(self, clean_memory_data):
        """Full end-to-end consolidation test with real Ollama.

        Steps:
        1. Boot MemoryArchitecture with isolated DB
        2. Store 6+ episodic memories about Akash (repeatable facts)
        3. Subscribe to consolidation.completed event
        4. Call ConsolidationEngine.consolidate_cycle() directly
        5. Assert: facts extracted (confidence >= 0.7, evidence_count >= 2)
        6. Assert: patterns extracted
        7. Assert: consolidation_log record exists
        8. Second pass: store more episodes, verify reinforcement
        """
        import yaml
        from sentient.core.event_bus import EventBus, reset_event_bus
        from sentient.core.inference_gateway import InferenceGateway
        from sentient.memory.architecture import MemoryArchitecture
        from sentient.sleep.consolidation import ConsolidationEngine

        reset_event_bus()
        event_bus = EventBus()

        # Load configs
        config_dir = Path(
            __import__("os").environ.get(
                "SENTIENT_CONFIG_DIR",
                str(Path(__file__).resolve().parent.parent.parent / "config"),
            )
        )
        with open(config_dir / "inference_gateway.yaml") as f:
            inference_cfg = yaml.safe_load(f)

        # Configure memory to use isolated tmp path
        memory_cfg = {
            "storage": {
                "sqlite_path": clean_memory_data["sqlite_path"],
                "chroma_path": clean_memory_data["chroma_path"],
            },
            "embeddings": {"model": "all-MiniLM-L6-v2"},
            "gatekeeper": {},
        }

        # Initialize inference gateway
        inference_gateway = InferenceGateway(inference_cfg)
        await inference_gateway.initialize()

        # Initialize memory architecture
        memory = MemoryArchitecture(memory_cfg, event_bus)
        await memory.initialize()
        await memory.start()

        # Initialize consolidation engine
        consolidation_engine = ConsolidationEngine(
            memory_architecture=memory,
            inference_gateway=inference_gateway,
            event_bus=event_bus,
            config={
                "min_new_episodes": 6,
                "confidence_threshold_semantic": 0.7,
                "confidence_threshold_procedural": 0.6,
                "llm_call_timeout_seconds": 30,
                "semantic_similarity_threshold": 0.9,
                "consolidation_weight_bump": 0.1,
            },
        )

        # === STEP 1: Store 6+ episodic memories about Akash ===
        episodic_facts = [
            ("Hi, I'm Akash, I build this AI framework.", "user_identity"),
            ("My name is Akash and I'm the primary user.", "user_identity"),
            ("I come from a biology background, not CS.", "background"),
            ("Biology is my original training before getting into AI.", "background"),
            ("I prefer biological analogies when explaining technical concepts.", "preference"),
            ("When I explain things I often use biological metaphors.", "preference"),
        ]

        episode_ids = []
        now = time.time()
        for content, tag in episodic_facts:
            memory_id = await memory.store({
                "type": "episodic",
                "content": content,
                "importance": 0.7,
                "entity_tags": [tag],
                "created_at": now,
            })
            if memory_id:
                episode_ids.append(memory_id)

        assert len(episode_ids) >= 6, f"Expected >= 6 episodes stored, got {len(episode_ids)}"

        # === STEP 2: Subscribe to consolidation events ===
        cycle_complete_payload = {"fired": False, "payload": None}
        cycle_start_payload = {"fired": False, "payload": None}

        async def on_cycle_complete(payload):
            cycle_complete_payload["fired"] = True
            cycle_complete_payload["payload"] = payload

        async def on_cycle_start(payload):
            cycle_start_payload["fired"] = True
            cycle_start_payload["payload"] = payload

        await event_bus.subscribe("sleep.consolidation.cycle_complete", on_cycle_complete)
        await event_bus.subscribe("sleep.consolidation.cycle_start", on_cycle_start)

        # === STEP 3: Trigger consolidation directly ===
        result = await consolidation_engine.consolidate_cycle()

        # Small delay to let async event handlers run
        await asyncio.sleep(0.5)

        # === STEP 4: Verify results ===
        assert result["status"] == "completed", f"Expected completed, got {result}"
        assert result["facts_extracted"] >= 2, (
            f"Expected >= 2 facts extracted, got {result.get('facts_extracted', 0)}"
        )
        assert result["patterns_extracted"] >= 1, (
            f"Expected >= 1 pattern extracted, got {result.get('patterns_extracted', 0)}"
        )

        # Verify events fired
        assert cycle_complete_payload["fired"], "cycle_complete event did not fire"
        assert cycle_start_payload["fired"], "cycle_start event did not fire"

        # === STEP 5: Verify semantic facts in store ===
        semantic_facts = await memory.semantic_store.list_all()
        assert len(semantic_facts) >= 2, f"Expected >= 2 semantic facts, got {len(semantic_facts)}"

        high_confidence_facts = [
            f for f in semantic_facts
            if f.get("confidence", 0) >= 0.7 and f.get("evidence_count", 0) >= 2
        ]
        assert len(high_confidence_facts) >= 2, (
            f"Expected >= 2 facts with confidence >= 0.7 and evidence_count >= 2, "
            f"got {len(high_confidence_facts)}: {semantic_facts}"
        )

        # === STEP 6: Verify procedural patterns in store ===
        procedural_patterns = await memory.procedural_store.list_all()
        assert len(procedural_patterns) >= 1, (
            f"Expected >= 1 procedural pattern, got {len(procedural_patterns)}"
        )

        # === STEP 7: Verify consolidation_log record ===
        rows = memory._conn.execute(
            "SELECT id, consolidated_at, scope, summary_content, source_memory_count FROM consolidation_log"
        ).fetchall()
        assert len(rows) == 1, f"Expected 1 consolidation_log entry, got {len(rows)}"
        assert rows[0]["scope"] == "daily"
        assert rows[0]["source_memory_count"] >= 6

        # === STEP 8: Cross-turn reinforcement ===
        more_facts = [
            ("I push back on over-engineering in software design.", "preference"),
            ("I believe in minimal viable solutions over complex ones.", "preference"),
            ("I work iteratively, one module at a time.", "working_style"),
            ("My development approach is incremental and modular.", "working_style"),
            ("I'm Akash, the creator and primary user of this system.", "user_identity"),
            ("My name is Akash and I have a biology background.", "background"),
        ]

        for content, tag in more_facts:
            await memory.store({
                "type": "episodic",
                "content": content,
                "importance": 0.7,
                "entity_tags": [tag],
                "created_at": time.time(),
            })

        # Reset event tracking
        cycle_complete_payload["fired"] = False
        cycle_start_payload["fired"] = False

        result_2 = await consolidation_engine.consolidate_cycle()
        await asyncio.sleep(0.5)

        assert result_2["status"] == "completed"

        semantic_facts_2 = await memory.semantic_store.list_all()
        assert len(semantic_facts_2) >= len(semantic_facts)

        # Check that some existing facts were reinforced
        for fact in semantic_facts_2:
            if fact.get("reinforcement_count", 1) > 1:
                break
        else:
            pytest.fail("Expected at least one fact to be reinforced in second consolidation")

        print("\n=== WETWARE CONSOLIDATION TEST SUMMARY ===")
        print(f"Episodes stored: {len(episode_ids) + 6}")
        print(f"Semantic facts extracted: {len(semantic_facts)}")
        print(f"Procedural patterns extracted: {len(procedural_patterns)}")
        print(f"Consolidation log entries: {len(rows)}")
        print(f"Events fired: cycle_start={cycle_start_payload['fired']}, cycle_complete={cycle_complete_payload['fired']}")

        # Cleanup
        await memory.shutdown()
        await inference_gateway.shutdown()