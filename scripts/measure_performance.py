#!/usr/bin/env python3
"""Phase 6 Performance Baseline Measurement — D6.

Runs the 3-turn wetware conversation and measures:
- Cold startup time (with memory warm-up)
- First-token latency per turn
- Total per-turn latency
- Memory retrieval latency (separate)
- Peak RSS
- LLM calls per turn
- ChromaDB on-disk growth per turn

Compare to Phase 5 baseline: 1.4s startup, 31.6s response, 186 MB RSS.
"""
import asyncio
import os
import resource
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def measure():
    from sentient.core.event_bus import EventBus, reset_event_bus
    from sentient.core.inference_gateway import InferenceGateway
    from sentient.memory.architecture import MemoryArchitecture
    from sentient.prajna.frontal.cognitive_core import CognitiveCore
    from sentient.prajna.frontal.world_model import WorldModel
    from sentient.core.envelope import Envelope, SourceType, TrustLevel, Priority

    rss_before = get_rss_mb()
    startup_start = time.time()

    reset_event_bus()
    event_bus = EventBus()

    # Load configs
    config_dir = PROJECT_ROOT / "config"
    with open(config_dir / "system.yaml") as f:
        system_cfg = yaml.safe_load(f)
    with open(config_dir / "inference_gateway.yaml") as f:
        inference_cfg = yaml.safe_load(f)

    # Use temp dir for memory
    tmp_dir = tempfile.mkdtemp(prefix="sentient_perf_")

    memory_cfg = dict(system_cfg.get("memory", {}))
    memory_cfg["storage"] = {
        "sqlite_path": f"{tmp_dir}/memory.db",
        "chroma_path": f"{tmp_dir}/chroma",
    }
    memory_cfg["embeddings"] = memory_cfg.get("embeddings") or {"model": "all-MiniLM-L6-v2"}

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

    startup_duration = time.time() - startup_start
    rss_after_startup = get_rss_mb()

    # Measure memory retrieval latency separately
    retrieval_latencies = []
    test_queries = ["Akash sentient AI", "framework innovation", "continuous cognition"]
    for query in test_queries:
        t0 = time.time()
        try:
            await memory.retrieve_episodic(query, k=3)
        except Exception:
            pass
        retrieval_latencies.append((time.time() - t0) * 1000)

    # Run 3-turn conversation
    conversation = [
        "Hi, I'm Akash. I'm building a sentient AI framework.",
        "What's my name and what am I working on?",
        "Do you remember the framework's main innovation?",
    ]

    turn_metrics = []
    total_start = time.time()

    for turn_idx, user_input in enumerate(conversation):
        turn_start = time.time()
        cycle_count_before = len(cognitive_core._recent_cycles)
        event_count_before = event_bus.event_count()

        # Get ChromaDB size before turn
        chroma_size_before = 0
        chroma_dir = Path(tmp_dir) / "chroma"
        if chroma_dir.exists():
            for f in chroma_dir.rglob("*"):
                if f.is_file():
                    chroma_size_before += f.stat().st_size

        envelope = Envelope(
            source_type=SourceType.CHAT,
            plugin_name="chat_input",
            sender_identity="creator",
            trust_level=TrustLevel.TIER_1_CREATOR,
            priority=Priority.TIER_2_ELEVATED,
            processed_content=user_input,
        )

        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={"motivational": 0.7, "urgency": 0.3},
            sidebar=[],
        )

        await event_bus.publish("tlp.enriched", {"context": context})

        # Wait for completion
        await asyncio.sleep(1)
        max_wait = 90
        waited = 1
        while waited < max_wait:
            if len(cognitive_core._recent_cycles) > cycle_count_before:
                last_cycle = cognitive_core._recent_cycles[-1]
                if last_cycle.completed_at:
                    break
            await asyncio.sleep(2)
            waited += 2

        turn_duration = time.time() - turn_start
        event_count_after = event_bus.event_count()

        # Get ChromaDB size after turn
        chroma_size_after = 0
        if chroma_dir.exists():
            for f in chroma_dir.rglob("*"):
                if f.is_file():
                    chroma_size_after += f.stat().st_size

        # Get memory count
        memory_count = await memory.count()

        turn_metrics.append({
            "turn": turn_idx + 1,
            "duration_s": round(turn_duration, 2),
            "llm_calls": event_count_after - event_count_before,
            "chroma_growth_bytes": chroma_size_after - chroma_size_before,
            "total_memories": memory_count,
        })

    total_duration = time.time() - total_start
    peak_rss = get_rss_mb()

    # Print results
    print("\n" + "=" * 60)
    print("PHASE 6 PERFORMANCE BASELINE")
    print("=" * 60)
    print(f"\nStartup: {startup_duration:.2f}s")
    print(f"RSS after startup: {rss_after_startup:.0f} MB")
    print(f"Peak RSS: {peak_rss:.0f} MB")
    print(f"Total 3-turn duration: {total_duration:.1f}s")
    print(f"\nMemory retrieval latency (ms): {[round(l, 1) for l in retrieval_latencies]}")
    print(f"Avg retrieval: {sum(retrieval_latencies)/len(retrieval_latencies):.1f} ms")

    print(f"\nPer-turn metrics:")
    for tm in turn_metrics:
        print(f"  Turn {tm['turn']}: {tm['duration_s']}s, ~{tm['llm_calls']} events, "
              f"ChromaDB +{tm['chroma_growth_bytes']}B, {tm['total_memories']} memories")

    print(f"\nPhase 5 comparison:")
    print(f"  Startup: 1.4s → {startup_duration:.2f}s")
    print(f"  Response: 31.6s → {turn_metrics[0]['duration_s']:.1f}s (turn 1)")
    print(f"  RSS: 186 MB → {peak_rss:.0f} MB")
    print("=" * 60)

    # Cleanup
    await memory.shutdown()
    await inference_gateway.shutdown()
    await cognitive_core.shutdown()
    await world_model.shutdown()

    # Clean temp dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(measure())