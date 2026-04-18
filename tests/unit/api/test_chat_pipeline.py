"""Step-wise integration tests for the full chat pipeline.

Traces the path from API -> ChatInput -> Thalamus -> Checkpost -> QueueZone -> TLP -> CognitiveCore -> WorldModel -> Brainstem -> ChatOutput -> API.
"""
import asyncio
import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.api.server import APIServer
from sentient.brainstem.gateway import Brainstem
from sentient.brainstem.plugins.chat_output import ChatOutputPlugin
from sentient.core.event_bus import get_event_bus, reset_event_bus
from sentient.core.inference_gateway import InferenceGateway
from sentient.prajna.checkpost import Checkpost
from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.prajna.frontal.world_model import WorldModel
from sentient.prajna.queue_zone import QueueZone
from sentient.prajna.temporal_limbic import TemporalLimbicProcessor
from sentient.thalamus.gateway import Thalamus
from sentient.thalamus.plugins.chat_input import ChatInputPlugin


@pytest.fixture
async def full_pipeline():
    """Builds a pipeline with real modules and mocked InferenceGateway."""
    reset_event_bus()
    event_bus = get_event_bus()

    # Mocks
    mock_gateway = AsyncMock(spec=InferenceGateway)

    # Cognitive Core Response
    cc_response = MagicMock()
    cc_response.text = json.dumps({
        "monologue": "Thinking about the user's message.",
        "assessment": "User said hello.",
        "decisions": [{
            "type": "respond",
            "text": "Hello! How can I help you today?",
            "goal": "",
            "context": "",
            "success_criteria": "",
            "rationale": "Greeting the user.",
            "priority": "high"
        }],
        "reflection": {
            "confidence": 0.9,
            "uncertainties": [],
            "novelty": 0.1,
            "memory_candidates": []
        }
    })
    cc_response.error = None

    # World Model Response
    wm_response = MagicMock()
    wm_response.text = json.dumps({
        "verdict": "approved",
        "dimension_assessments": {
            "feasibility": {"score": 1.0, "notes": "OK"},
            "consequence": {"score": 1.0, "notes": "OK"},
            "ethics": {"score": 1.0, "notes": "OK"},
            "consistency": {"score": 1.0, "notes": "OK"},
            "reality_grounding": {"score": 1.0, "notes": "OK"}
        },
        "advisory_notes": "",
        "revision_guidance": "",
        "veto_reason": "",
        "confidence": 1.0
    })
    wm_response.error = None

    # Configure mock gateway to return different responses based on model_label
    async def side_effect(request):
        if request.model_label == "cognitive-core":
            return cc_response
        elif request.model_label == "world-model":
            return wm_response
        return MagicMock(text="{}", error=None)

    mock_gateway.infer.side_effect = side_effect

    # Initialize Modules
    config = {
        "thalamus": {
            "batching": {
                "min_window_seconds": 0.1,
                "default_window_seconds": 0.1,
                "max_window_seconds": 1.0
            },
            "heuristic_engine": {
                "tier1_keywords": ["emergency", "shutdown"]
            }
        },
        "queue_zone": {"starvation": {"age_to_tier2_seconds": 1}},
        "tlp": {},
        "cognitive_core": {"daydream": {"enabled": False}},
        "world_model": {},
        "brainstem": {},
        "api": {"host": "127.0.0.1", "port": 8765}
    }

    thalamus = Thalamus(config["thalamus"], event_bus)
    checkpost = Checkpost(config["checkpost"] if "checkpost" in config else {}, mock_gateway, event_bus=event_bus)
    queue_zone = QueueZone(config["queue_zone"], event_bus)
    tlp = TemporalLimbicProcessor(config["tlp"], mock_gateway, event_bus=event_bus)
    cognitive_core = CognitiveCore(config["cognitive_core"], mock_gateway, event_bus=event_bus)
    world_model = WorldModel(config["world_model"], mock_gateway, event_bus=event_bus)
    brainstem = Brainstem(config["brainstem"], event_bus)

    # Register modules
    await thalamus.initialize()
    await checkpost.initialize()
    await queue_zone.initialize()
    await tlp.initialize()
    await cognitive_core.initialize()
    await world_model.initialize()
    await brainstem.initialize()

    # Plugins
    chat_input = ChatInputPlugin()
    chat_output = ChatOutputPlugin()
    await thalamus.register_plugin(chat_input)
    await brainstem.register_plugin(chat_output)

    # Start modules
    await thalamus.start()
    await checkpost.start()
    await queue_zone.start()
    await tlp.start()
    await cognitive_core.start()
    await world_model.start()
    await brainstem.start()

    # API Server
    lifecycle = MagicMock()
    health_network = MagicMock()
    health_network.snapshot.return_value = {}

    server = APIServer(
        config["api"],
        lifecycle,
        chat_input,
        chat_output,
        health_network,
        event_bus=event_bus
    )
    # We don't call server.start() because it spawns background tasks that might interfere.
    # We manually subscribe to broadcast events like the real server does.
    await event_bus.subscribe("*", server._broadcast_event)

    return {
        "server": server,
        "chat_input": chat_input,
        "chat_output": chat_output,
        "event_bus": event_bus,
        "gateway": mock_gateway,
        "thalamus": thalamus,
        "queue_zone": queue_zone,
    }


@pytest.mark.asyncio
async def test_full_pipeline_step_by_step(full_pipeline):
    """Verifies that a message flows through every stage of the pipeline."""
    pipeline = full_pipeline
    server = pipeline["server"]
    chat_input = pipeline["chat_input"]
    event_bus = pipeline["event_bus"]

    # Track events to verify each stage
    received_events = []
    async def tracker(payload):
        received_events.append(payload.get("event_type"))

    await event_bus.subscribe("*", tracker)

    # 1. Inject message via API (simulated)
    turn_id = str(uuid.uuid4())
    message = {
        "text": "Hello Sentient emergency shutdown",
        "turn_id": turn_id,
        "session_id": "test-session"
    }

    # Manually trigger what API does
    await chat_input.inject(message)
    await event_bus.publish("chat.input.received", {"turn_id": turn_id, **message})

    # Wait for the pipeline to process
    # Stages:
    # - input.received (Thalamus)
    # - input.classified (Thalamus)
    # - checkpost.tagged (Checkpost)
    # - input.delivered (QueueZone)
    # - tlp.enriched (TLP)
    # - cognitive.cycle.start (CognitiveCore)
    # - decision.proposed (CognitiveCore)
    # - decision.reviewed (WorldModel)
    # - decision.approved (WorldModel)
    # - action.executed (Brainstem)

    # We need to wait enough for asyncio tasks to run.
    # QueueZone has a 2s loop, so we might need to wait more than 2s or
    # manually trigger delivery if possible.
    # Let's try waiting 3 seconds.

    max_wait = 5.0
    start_time = time.time()
    required_events = {
        "chat.input.received",
        "input.classified",
        "checkpost.tagged",
        "input.delivered",
        "tlp.enriched",
        "cognitive.cycle.start",
        "decision.proposed",
        "decision.approved",
        "action.executed"
    }

    while not required_events.issubset(set(received_events)) and time.time() - start_time < max_wait:
        await asyncio.sleep(0.1)

    print(f"Received events: {received_events}")

    # Verify events
    assert "chat.input.received" in received_events
    assert "input.classified" in received_events
    assert "checkpost.tagged" in received_events
    assert "input.delivered" in received_events
    assert "tlp.enriched" in received_events
    assert "cognitive.cycle.start" in received_events
    assert "decision.proposed" in received_events
    assert "decision.approved" in received_events
    assert "action.executed" in received_events

    # 2. Check ChatOutputPlugin queue
    chat_output = pipeline["chat_output"]
    assert chat_output.outgoing_queue.qsize() == 1
    out_msg = await chat_output.outgoing_queue.get()
    assert out_msg["type"] == "chat_message"
    assert "Hello! How can I help you today?" in out_msg["text"]

    # 3. Test API _drain_outgoing
    # Mock WebSocket
    mock_ws = AsyncMock()
    server._ws_clients.add(mock_ws)

    # Put the message back in for drain to pick up
    await chat_output.outgoing_queue.put(out_msg)

    # Run drain iteration
    # Since _drain_outgoing is a while True loop, we run it as a task and cancel it.
    drain_task = asyncio.create_task(server._drain_outgoing())
    await asyncio.sleep(0.1)
    drain_task.cancel()

    # Verify WS received the reply
    mock_ws.send_json.assert_called()
    # Check if any call contains the reply
    found_reply = False
    for call in mock_ws.send_json.call_args_list:
        if call[0][0]["type"] == "reply":
            assert "Hello! How can I help you today?" in call[0][0]["text"]
            found_reply = True
            break
    assert found_reply, "No 'reply' message sent to WebSocket"


@pytest.mark.asyncio
async def test_queue_zone_delivery_wait(full_pipeline):
    """Specifically tests that QueueZone delivers messages."""
    pipeline = full_pipeline
    event_bus = pipeline["event_bus"]
    queue_zone = pipeline["queue_zone"]

    delivered = asyncio.Event()
    async def on_delivered(payload):
        delivered.set()

    await event_bus.subscribe("input.delivered", on_delivered)

    # Mock envelope
    from sentient.core.envelope import Envelope, SourceType, TrustLevel
    envelope = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="user",
        trust_level=TrustLevel.TIER_1_CREATOR,
        raw_content={"text": "test"},
        processed_content="test"
    )

    await queue_zone.enqueue(envelope)

    # Wait for delivery loop (which runs every 2s)
    try:
        await asyncio.wait_for(delivered.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        pytest.fail("QueueZone failed to deliver message within timeout")
