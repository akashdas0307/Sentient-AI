"""Wetware test D4: First real conversation with the sentient framework.

Requires: Ollama running locally with glm-5.1:cloud and minimax-m2.7:cloud models.
Run: pytest -m wetware tests/wetware/test_first_conversation.py -v
"""
from __future__ import annotations

import asyncio
import time

import pytest

pytestmark = pytest.mark.wetware


@pytest.mark.wetware
@pytest.mark.asyncio
async def test_first_conversation(real_gateway):
    """Have the first real conversation with the sentient framework."""
    from sentient.core.event_bus import EventBus
    from sentient.core.lifecycle import LifecycleManager
    from sentient.thalamus.gateway import Thalamus
    from sentient.thalamus.plugins.chat_input import ChatInputPlugin
    from sentient.prajna.checkpost import Checkpost
    from sentient.prajna.queue_zone import QueueZone
    from sentient.prajna.temporal_limbic import TemporalLimbicProcessor
    from sentient.prajna.frontal.cognitive_core import CognitiveCore
    from sentient.prajna.frontal.world_model import WorldModel
    from sentient.brainstem.gateway import Brainstem
    from sentient.brainstem.plugins.chat_output import ChatOutputPlugin

    bus = EventBus()
    lifecycle = LifecycleManager(bus)

    batch_config = {
        "batching": {"default_window_seconds": 0.1, "min_window_seconds": 0.05, "max_window_seconds": 0.2},
        "heuristic_engine": {"tier1_keywords": ["urgent", "emergency"]},
    }

    thalamus = Thalamus(batch_config, bus)
    checkpost = Checkpost({}, real_gateway, None, bus)
    queue_zone = QueueZone({}, bus)
    tlp = TemporalLimbicProcessor({}, real_gateway, None, bus)
    cognitive = CognitiveCore({}, real_gateway, persona=None, memory=None, event_bus=bus)
    world_model = WorldModel({}, real_gateway, persona=None, event_bus=bus)
    brainstem = Brainstem({}, bus)
    chat_output = ChatOutputPlugin()

    # Register real_gateway in lifecycle (CRITICAL — must come before other modules)
    lifecycle.register(real_gateway)
    for mod in [thalamus, checkpost, queue_zone, tlp, cognitive, world_model, brainstem]:
        lifecycle.register(mod)

    await lifecycle.startup()
    chat_input = ChatInputPlugin()
    await thalamus.register_plugin(chat_input)
    await brainstem.register_plugin(chat_output)

    # --- First message: "Hello, who are you?" ---
    start_time_1 = time.time()
    await chat_input.inject({"text": "urgent: Hello, who are you?"})

    # Poll queue until we get a response or timeout (120s for real LLM calls)
    deadline = asyncio.get_running_loop().time() + 120
    output_messages = []
    poll_count = 0
    while asyncio.get_running_loop().time() < deadline:
        poll_count += 1
        await asyncio.sleep(2)
        queue_size = chat_output.outgoing_queue.qsize()
        while not chat_output.outgoing_queue.empty():
            output_messages.append(await chat_output.outgoing_queue.get())
        if output_messages:
            break
        if poll_count % 5 == 0:
            print(f"  [poll {poll_count}] still waiting... queue_size={queue_size}")

    latency_1 = time.time() - start_time_1

    # Validate first response
    assert len(output_messages) >= 1, "No response received for first message"
    first_response = output_messages[0]
    assert first_response.get("text"), "Empty response text for first message"
    response_text_1 = first_response["text"]

    # Ensure we got actual text, not raw JSON leak
    assert not response_text_1.strip().startswith("{"), f"Response appears to be raw JSON: {response_text_1[:100]}"

    print(f"\n[First response] latency={latency_1:.1f}s, text={response_text_1[:200]}...")

    # --- Follow-up: "What did I just ask you?" ---
    start_time_2 = time.time()
    await chat_input.inject({"text": "urgent: What did I just ask you?"})

    deadline = asyncio.get_running_loop().time() + 120
    output_messages_2 = []
    poll_count_2 = 0
    while asyncio.get_running_loop().time() < deadline:
        poll_count_2 += 1
        await asyncio.sleep(2)
        while not chat_output.outgoing_queue.empty():
            output_messages_2.append(await chat_output.outgoing_queue.get())
        if output_messages_2:
            break
        if poll_count_2 % 5 == 0:
            print(f"  [poll {poll_count_2}] follow-up still waiting...")

    latency_2 = time.time() - start_time_2

    # Validate follow-up response
    assert len(output_messages_2) >= 1, "No response received for follow-up message"
    second_response = output_messages_2[0]
    assert second_response.get("text"), "Empty response text for follow-up message"
    response_text_2 = second_response["text"]

    print(f"\n[Follow-up response] latency={latency_2:.1f}s, text={response_text_2[:200]}...")

    # --- Capture metrics ---
    model_used = first_response.get("metadata", {}).get("model_used", "unknown")
    print(f"\n[Conversation complete] model_used={model_used}")

    # --- Cleanup ---
    await lifecycle.shutdown()

    print("\n[PASS] test_first_conversation completed successfully")
