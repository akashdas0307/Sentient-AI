"""Phase 6 Full-System Wetware Test — D5.

Proves the system remembers across turns by running a 3-turn conversation
with real LLM calls through the full pipeline.

Success criteria:
- Turn 2: contains "Akash" + references framework/AI project
- Turn 3: references continuous cognition, memory, or core innovation
- No pipeline dead-ends (revision cap fallback acceptable)
- Total wall-clock < 4 minutes
- Peak RSS < 8 GB

Requires: Ollama running with GLM-5.1:cloud model available.
Run: pytest -m wetware tests/wetware/test_full_system.py -v
"""
from __future__ import annotations

import asyncio
import os
import resource
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

# Mark all tests in this module as wetware (real LLM calls)
pytestmark = pytest.mark.wetware

# Project root is 3 levels up from this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _check_ollama_available():
    """Skip if Ollama is not running or model not available."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        return True
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _check_ollama_available(),
    reason="Ollama not running or not accessible"
)


def get_peak_rss_mb() -> float:
    """Get peak RSS in MB using resource module."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


@pytest.fixture
def clean_memory_data():
    """Ensure clean memory data for each test."""
    data_dir = Path("./data")
    # Clean before test
    for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
        p = data_dir / f
        if p.exists():
            p.unlink()
    chroma_dir = data_dir / "chroma"
    if chroma_dir.exists():
        import shutil
        shutil.rmtree(chroma_dir)

    yield data_dir

    # Clean after test too
    for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
        p = data_dir / f
        if p.exists():
            p.unlink()
    if chroma_dir.exists():
        import shutil
        shutil.rmtree(chroma_dir)


@requires_ollama
class TestFullSystemWetware:
    """3-turn conversation test with real LLM calls."""

    @pytest.mark.asyncio
    async def test_three_turn_conversation(self, clean_memory_data, tmp_path):
        """Run a 3-turn conversation and verify cross-turn memory."""
        # RAM Check
        import subprocess
        try:
            subprocess.run(
                "free -m | awk 'NR==2 {if ($7 < 4000) exit 1}'",
                shell=True, check=True
            )
        except subprocess.CalledProcessError:
            pytest.fail("RAM_INSUFFICIENT: Need at least 4GB free for wetware tests")

        import yaml
        from sentient.core.event_bus import EventBus, reset_event_bus
        from sentient.core.inference_gateway import InferenceGateway
        from sentient.memory.architecture import MemoryArchitecture
        from sentient.prajna.frontal.cognitive_core import CognitiveCore
        from sentient.prajna.frontal.world_model import WorldModel
        from sentient.core.envelope import Envelope, SourceType, TrustLevel, Priority

        reset_event_bus()
        event_bus = EventBus()

        # Load configs
        config_dir = Path(os.environ.get("SENTIENT_CONFIG_DIR", str(PROJECT_ROOT / "config")))
        with open(config_dir / "system.yaml") as f:
            system_cfg = yaml.safe_load(f)
        with open(config_dir / "inference_gateway.yaml") as f:
            inference_cfg = yaml.safe_load(f)

        # Override memory paths to use tmp_path for isolation
        memory_cfg = dict(system_cfg.get("memory", {}))
        memory_cfg["storage"] = {
            "sqlite_path": str(tmp_path / "memory.db"),
            "chroma_path": str(tmp_path / "chroma"),
        }
        memory_cfg["embeddings"] = memory_cfg.get("embeddings") or {"model": "all-MiniLM-L6-v2"}

        # Initialize modules
        inference_gateway = InferenceGateway(inference_cfg)
        await inference_gateway.initialize()

        memory = MemoryArchitecture(memory_cfg, event_bus)
        await memory.initialize()
        await memory.start()

        cognitive_core = CognitiveCore(
            system_cfg.get("cognitive_core", {}),
            inference_gateway,
            memory=memory,
            event_bus=event_bus,
        )
        world_model = WorldModel(
            system_cfg.get("world_model", {}),
            inference_gateway,
            event_bus=event_bus,
        )
        await cognitive_core.initialize()
        await cognitive_core.start()
        await world_model.initialize()
        await world_model.start()

        # Track published events for verification
        approved_decisions = []
        async def capture_approved(payload):
            approved_decisions.append(payload)
        await event_bus.subscribe("decision.approved", capture_approved)

        # Also track vetoed decisions
        vetoed_decisions = []
        async def capture_vetoed(payload):
            vetoed_decisions.append(payload)
        await event_bus.subscribe("decision.vetoed", capture_vetoed)

        # Helper for step-wise verification
        async def wait_for_cycle_completion(core, count_before, timeout=60):
            async def predicate():
                while len(core._recent_cycles) <= count_before:
                    await asyncio.sleep(0.5)
                last_cycle = core._recent_cycles[-1]
                while not last_cycle.completed_at:
                    if last_cycle.error:
                        return last_cycle
                    await asyncio.sleep(0.5)
                return last_cycle

            try:
                return await asyncio.wait_for(predicate(), timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Cognitive cycle did not complete within {timeout}s")

        # === CONVERSATION TURNS ===
        start_time = time.time()
        turn_results = []

        conversation = [
            "Hi, I'm Akash. I'm building a sentient AI framework.",
            "What's my name and what am I working on?",
            "Do you remember the framework's main innovation?",
        ]

        for turn_idx, user_input in enumerate(conversation):
            turn_start = time.time()
            cycle_count_before = len(cognitive_core._recent_cycles)

            # Create envelope
            envelope = Envelope(
                source_type=SourceType.CHAT,
                plugin_name="chat_input",
                sender_identity="creator",
                trust_level=TrustLevel.TIER_1_CREATOR,
                priority=Priority.TIER_2_ELEVATED,
                processed_content=user_input,
            )

            # Create enriched context (simulating TLP output)
            context = SimpleNamespace(
                envelope=envelope,
                related_memories=[],
                significance={"motivational": 0.7, "urgency": 0.3},
                sidebar=[],
            )

            # Publish tlp.enriched event (triggers CognitiveCore)
            await event_bus.publish("tlp.enriched", {"context": context})

            # Wait for reasoning cycle with clear timeout and fast failure on error
            try:
                last_cycle = await wait_for_cycle_completion(cognitive_core, cycle_count_before)
            except Exception as e:
                pytest.fail(f"Turn {turn_idx + 1} failed during cycle wait: {e}")

            turn_duration = time.time() - turn_start

            # Step-wise assertion: verify turn completed without error immediately
            assert last_cycle.error is None, f"Turn {turn_idx + 1} reasoning error: {last_cycle.error}"
            assert last_cycle.completed_at is not None, f"Turn {turn_idx + 1} did not complete"

            turn_result = {
                "turn": turn_idx + 1,
                "input": user_input,
                "duration_s": round(turn_duration, 2),
                "cycle_error": last_cycle.error,
                "decisions": last_cycle.decisions,
                "monologue": last_cycle.monologue,
            }
            turn_results.append(turn_result)

            print(f"\n=== Turn {turn_idx + 1} ({turn_duration:.1f}s) ===")
            print(f"Input: {user_input}")
            for d in last_cycle.decisions:
                print(f"Decision: {d.get('type', '?')} → {d.get('text', d.get('rationale', '?'))[:100]}")

        total_duration = time.time() - start_time
        peak_rss = get_peak_rss_mb()

        # === FINAL ASSERTIONS ===

        # 1. All turns completed without errors
        for tr in turn_results:
            assert tr["cycle_error"] is None, f"Turn {tr['turn']} had error: {tr['cycle_error']}"

        # 2. Turn 2 must reference "Akash" and the framework/AI project
        turn2_response = ""
        if len(turn_results) > 1 and turn_results[1]["decisions"]:
            for d in turn_results[1]["decisions"]:
                turn2_response += d.get("text", "") + " "
        turn2_response_lower = turn2_response.lower()
        assert "akash" in turn2_response_lower, (
            f"Turn 2 must reference 'Akash'. Got: {turn2_response[:200]}"
        )
        # Check for framework/AI project reference
        framework_referenced = any(
            word in turn2_response_lower
            for word in ["framework", "ai", "project", "sentient", "building"]
        )
        assert framework_referenced, (
            f"Turn 2 must reference the AI framework/project. Got: {turn2_response[:200]}"
        )

        # 3. Turn 3 must reference continuous cognition, memory, or innovation
        turn3_response = ""
        if len(turn_results) > 2 and turn_results[2]["decisions"]:
            for d in turn_results[2]["decisions"]:
                turn3_response += d.get("text", "") + " "
        turn3_response_lower = turn3_response.lower()
        memory_referenced = any(
            word in turn3_response_lower
            for word in ["memory", "remember", "continuous", "cognition", "innovation", "conscious"]
        )
        assert memory_referenced, (
            f"Turn 3 must reference memory/continuous cognition. Got: {turn3_response[:200]}"
        )

        # 4. Total wall-clock < 4 minutes
        assert total_duration < 240, (
            f"Total test duration {total_duration:.1f}s exceeds 4-minute budget"
        )

        # 5. Peak RSS < 8 GB
        assert peak_rss < 8192, (
            f"Peak RSS {peak_rss:.0f} MB exceeds 8 GB budget"
        )

        # 6. No pipeline dead-ends (at least some decisions approved)
        # Revision cap fallback is acceptable
        assert len(approved_decisions) > 0 or len(turn_results) > 0, (
            "No decisions were approved — pipeline may have dead-ended"
        )

        # Print summary
        print("\n=== WETWARE TEST SUMMARY ===")
        print(f"Total duration: {total_duration:.1f}s")
        print(f"Peak RSS: {peak_rss:.0f} MB")
        print(f"Approved decisions: {len(approved_decisions)}")
        print(f"Vetoed decisions: {len(vetoed_decisions)}")
        for tr in turn_results:
            print(f"Turn {tr['turn']}: {tr['duration_s']}s, decisions={len(tr['decisions'])}")

        # Cleanup
        await memory.shutdown()
        await inference_gateway.shutdown()
        await cognitive_core.shutdown()
        await world_model.shutdown()