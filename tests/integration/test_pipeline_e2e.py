"""End-to-end pipeline integration tests.

These tests verify that a message flows through the full pipeline:
ChatInput → Thalamus → Checkpost → QueueZone → TLP → CognitiveCore → WorldModel → Brainstem → ChatOutput

All LLM calls are mocked. The tests use the real EventBus and real Envelope objects
to verify the pub/sub wiring works correctly.
"""
from __future__ import annotations

import asyncio

import pytest

from sentient.core.envelope import Envelope, Priority, SourceType, TrustLevel
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


SHORT_BATCH_CONFIG = {
    "batching": {
        "default_window_seconds": 0.1,
        "min_window_seconds": 0.05,
        "max_window_seconds": 0.2,
    },
    "heuristic_engine": {"tier1_keywords": ["urgent", "emergency"]},
}


@pytest.mark.asyncio
async def test_thalamus_to_checkpost_pipeline(bus, gateway):
    """Test that Thalamus forwards envelopes to Checkpost via EventBus."""
    lifecycle = LifecycleManager(bus)

    events_received = []

    async def track_event(payload):
        events_received.append(payload)

    await bus.subscribe("input.classified", track_event)

    thalamus = Thalamus(SHORT_BATCH_CONFIG, bus)
    checkpost = Checkpost({}, gateway, None, bus)

    lifecycle.register(thalamus)
    lifecycle.register(checkpost)
    await lifecycle.startup()

    chat_input = ChatInputPlugin()
    await thalamus.register_plugin(chat_input)

    # Use urgency keyword → Tier 1 → bypasses batching
    await chat_input.inject({"text": "urgent: Hello, how are you?"})
    await asyncio.sleep(0.3)

    assert len(events_received) >= 1
    envelope = events_received[0]["envelope"]
    assert "urgent" in envelope.processed_content.lower()
    assert envelope.priority == Priority.TIER_1_IMMEDIATE

    await lifecycle.shutdown()


@pytest.mark.asyncio
async def test_checkpost_to_queue_zone_pipeline(bus, gateway):
    """Test that Checkpost publishes to QueueZone via EventBus."""
    events_received = []

    async def track_event(payload):
        events_received.append(payload)

    await bus.subscribe("checkpost.tagged", track_event)

    checkpost = Checkpost({}, gateway, None, bus)
    queue_zone = QueueZone({}, bus)

    await checkpost.initialize()
    await checkpost.start()
    await queue_zone.initialize()
    await queue_zone.start()

    envelope = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="Test message",
    )
    await bus.publish("input.classified", {"envelope": envelope})
    await asyncio.sleep(0.3)

    assert len(events_received) >= 1
    assert events_received[0]["envelope"] is envelope
    assert envelope.checkpost_processed is True

    await queue_zone.shutdown()


@pytest.mark.asyncio
async def test_full_pipeline_with_mocks(bus, gateway, memory, persona):
    """Full pipeline: message enters at ChatInput, exits at ChatOutput."""
    lifecycle = LifecycleManager(bus)

    event_types = [
        "input.classified", "checkpost.tagged", "input.delivered",
        "tlp.enriched", "cognitive.cycle.start", "decision.proposed",
        "decision.approved",
    ]
    events = {k: [] for k in event_types}

    async def track_event(payload, event_type):
        events[event_type].append(payload)

    for key in event_types:
        await bus.subscribe(key, lambda p, k=key: track_event(p, k))

    thalamus = Thalamus(SHORT_BATCH_CONFIG, bus)
    checkpost = Checkpost({}, gateway, memory, bus)
    queue_zone = QueueZone({}, bus)
    tlp = TemporalLimbicProcessor({}, gateway, memory, bus)
    cognitive = CognitiveCore({}, gateway, persona=persona, memory=memory, event_bus=bus)
    world_model = WorldModel({}, gateway, persona=persona, event_bus=bus)
    brainstem = Brainstem({}, bus)
    chat_output = ChatOutputPlugin()

    for mod in [thalamus, checkpost, queue_zone, tlp, cognitive, world_model, brainstem]:
        lifecycle.register(mod)

    await lifecycle.startup()

    chat_input = ChatInputPlugin()
    await thalamus.register_plugin(chat_input)
    await brainstem.register_plugin(chat_output)

    # Inject message with urgency keyword (Tier 1 bypasses batching)
    await chat_input.inject({"text": "urgent: What is your purpose?"})
    await asyncio.sleep(1.2)

    # Verify each pipeline stage was hit
    assert len(events["input.classified"]) >= 1, "Thalamus did not classify input"
    assert len(events["checkpost.tagged"]) >= 1, "Checkpost did not process input"
    assert len(events["input.delivered"]) >= 1, "QueueZone did not deliver to TLP"
    assert len(events["tlp.enriched"]) >= 1, "TLP did not enrich context"
    assert len(events["cognitive.cycle.start"]) >= 1, "CognitiveCore did not start cycle"
    assert len(events["decision.proposed"]) >= 1, "CognitiveCore did not propose decision"
    assert len(events["decision.approved"]) >= 1, "WorldModel did not approve decision"

    # Verify message reached chat output
    output_messages = []
    while not chat_output.outgoing_queue.empty():
        output_messages.append(await chat_output.outgoing_queue.get())

    assert len(output_messages) >= 1, "No message reached chat output"
    assert output_messages[0].get("text") == "Hello!"

    await lifecycle.shutdown()


@pytest.mark.asyncio
async def test_queue_zone_prioritization(bus):
    """Test that QueueZone respects priority tiers."""
    delivered_events = []

    async def track_delivery(payload):
        delivered_events.append(payload)

    await bus.subscribe("input.delivered", track_delivery)

    queue_zone = QueueZone({}, bus)
    await queue_zone.initialize()
    await queue_zone.start()

    # Tier 1 → immediate delivery
    t1_envelope = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="URGENT: help now!",
        priority=Priority.TIER_1_IMMEDIATE,
    )
    # Tier 3 → queued
    t3_envelope = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="Regular message",
        priority=Priority.TIER_3_NORMAL,
    )

    await queue_zone.enqueue(t3_envelope)
    await queue_zone.enqueue(t1_envelope)
    await asyncio.sleep(0.5)

    # At least the Tier 1 message should be delivered immediately
    assert len(delivered_events) >= 1

    await queue_zone.shutdown()


@pytest.mark.asyncio
async def test_world_model_veto_behavior(bus):
    """Test that WorldModel can veto a decision."""
    vetoed_events = []

    async def track_veto(payload):
        vetoed_events.append(payload)

    await bus.subscribe("decision.vetoed", track_veto)

    from tests.conftest import VetoingInferenceGateway
    gateway = VetoingInferenceGateway()
    world_model = WorldModel({}, gateway, None, bus)

    await world_model.initialize()
    await world_model.start()

    await bus.publish("decision.proposed", {
        "cycle_id": "test-cycle",
        "decision": {"type": "respond", "parameters": {"text": "bad"}, "rationale": "test", "priority": "high"},
    })
    await asyncio.sleep(0.3)

    assert len(vetoed_events) >= 1
    assert vetoed_events[0]["reason"] is not None

    await world_model.shutdown()


@pytest.mark.asyncio
async def test_envelope_metadata_enrichment(bus, gateway, memory):
    """Test that each pipeline stage enriches the envelope metadata."""
    checkpost = Checkpost({}, gateway, memory, bus)
    queue_zone = QueueZone({}, bus)
    tlp = TemporalLimbicProcessor({}, gateway, memory, bus)

    await checkpost.initialize()
    await checkpost.start()
    await queue_zone.initialize()
    await queue_zone.start()
    await tlp.initialize()
    await tlp.start()

    # Tier 1 envelope → bypasses QueueZone hold queue
    envelope = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="This is a test message that is long enough to trigger the LLM enhancement path in checkpost",
        priority=Priority.TIER_1_IMMEDIATE,
    )

    await bus.publish("input.classified", {"envelope": envelope})
    await asyncio.sleep(0.5)

    assert envelope.checkpost_processed is True, "Checkpost did not mark envelope"
    assert envelope.tlp_enriched is True, "TLP did not mark envelope"
    assert envelope.significance is not None, "TLP did not set significance"

    await tlp.shutdown()
    await queue_zone.shutdown()