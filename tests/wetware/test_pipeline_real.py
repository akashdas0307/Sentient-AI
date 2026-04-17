"""Wetware smoke test — sends Hello through full pipeline with real LLM calls.

Requires: Ollama running locally with glm-5.1:cloud and minimax-m2.7:cloud models.
Run: pytest -m wetware tests/wetware/
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.wetware


@pytest.mark.wetware
@pytest.mark.asyncio
async def test_real_pipeline_hello(real_gateway):
    """Send 'Hello' through the full pipeline using real LLM calls."""
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

    lifecycle.register(real_gateway)
    for mod in [thalamus, checkpost, queue_zone, tlp, cognitive, world_model, brainstem]:
        lifecycle.register(mod)

    await lifecycle.startup()
    chat_input = ChatInputPlugin()
    await thalamus.register_plugin(chat_input)
    await brainstem.register_plugin(chat_output)

    await chat_input.inject({"text": "urgent: Hello"})

    # Poll queue until we get a response or timeout (120s for real LLM calls)
    deadline = asyncio.get_running_loop().time() + 120
    output_messages = []
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(2)
        while not chat_output.outgoing_queue.empty():
            output_messages.append(await chat_output.outgoing_queue.get())
        if output_messages:
            break

    assert len(output_messages) >= 1, "No response from real pipeline"
    assert output_messages[0].get("text"), "Empty response from real pipeline"

    await lifecycle.shutdown()