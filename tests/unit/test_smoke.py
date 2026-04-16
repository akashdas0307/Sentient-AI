# ruff: noqa: F401
"""Smoke tests — verify the system scaffolding works.

These tests verify:
  - All modules can be imported without errors
  - Core primitives (event bus, envelope, lifecycle) function correctly
  - Module lifecycle contract is satisfied
  - A simple input flows through the envelope/event pipeline

These tests do NOT require actual LLM inference or external services.
"""
from __future__ import annotations

import asyncio
import pytest

from sentient.core.envelope import Envelope, Priority, SourceType, TrustLevel
from sentient.core.event_bus import EventBus
from sentient.core.lifecycle import LifecycleManager
from sentient.core.module_interface import ModuleInterface, ModuleStatus


@pytest.mark.asyncio
async def test_envelope_creation():
    """Envelope can be created with defaults."""
    env = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="Hello",
    )
    assert env.envelope_id
    assert env.is_from_creator()
    assert env.is_external()
    assert not env.is_expired()
    env.add_tag("intent", "greeting")
    assert "greeting" in env.intent_tags
    env.add_emotion("warmth", 0.6)
    assert env.emotional_tags["warmth"] == 0.6


@pytest.mark.asyncio
async def test_event_bus_pubsub():
    """Event bus delivers events to subscribers."""
    bus = EventBus()
    received = []

    async def handler(payload):
        received.append(payload)

    await bus.subscribe("test.event", handler)
    await bus.publish("test.event", {"value": 42})
    await asyncio.sleep(0.1)  # Let async handler run

    assert len(received) == 1
    assert received[0]["value"] == 42
    assert received[0]["event_type"] == "test.event"


@pytest.mark.asyncio
async def test_event_bus_wildcard():
    """Wildcard subscribers receive all events."""
    bus = EventBus()
    received = []

    async def handler(payload):
        received.append(payload["event_type"])

    await bus.subscribe("*", handler)
    await bus.publish("event.a", {})
    await bus.publish("event.b", {})
    await asyncio.sleep(0.1)

    assert "event.a" in received
    assert "event.b" in received


@pytest.mark.asyncio
async def test_event_bus_handler_exception_does_not_propagate():
    """A failing handler doesn't break the bus."""
    bus = EventBus()
    received = []

    async def bad_handler(payload):
        raise RuntimeError("boom")

    async def good_handler(payload):
        received.append(payload)

    await bus.subscribe("test", bad_handler)
    await bus.subscribe("test", good_handler)
    await bus.publish("test", {"x": 1})
    await asyncio.sleep(0.1)

    assert len(received) == 1


class _DummyModule(ModuleInterface):
    """Minimal test module."""

    def __init__(self, name="dummy"):
        super().__init__(name, {})
        self.initialized = False
        self.started = False
        self.shutdown_called = False

    async def initialize(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def shutdown(self):
        self.shutdown_called = True


@pytest.mark.asyncio
async def test_lifecycle_manager():
    """Lifecycle manager starts and shuts down modules."""
    bus = EventBus()
    lifecycle = LifecycleManager(bus)

    mod = _DummyModule("test_module")
    lifecycle.register(mod, essential=True)

    await lifecycle.startup()
    assert mod.initialized
    assert mod.started
    assert lifecycle.is_running()

    await lifecycle.shutdown()
    assert mod.shutdown_called


@pytest.mark.asyncio
async def test_module_health_pulse():
    """Module produces a valid health pulse."""
    mod = _DummyModule("test")
    pulse = mod.health_pulse()
    assert pulse.module_name == "test"
    assert pulse.status == ModuleStatus.HEALTHY
    assert "lifecycle_state" in pulse.metrics


def test_imports():
    """All major module packages can be imported."""
    # Core
    from sentient import core
    from sentient.core import envelope, event_bus, lifecycle, module_interface
    from sentient.core import inference_gateway

    # Thalamus
    from sentient import thalamus
    from sentient.thalamus import gateway, heuristic_engine
    from sentient.thalamus.plugins import chat_input, base

    # Prajñā
    from sentient import prajna
    from sentient.prajna import checkpost, queue_zone, temporal_limbic
    from sentient.prajna.frontal import cognitive_core, world_model, harness_adapter

    # Memory, Persona, Brainstem
    from sentient import memory, persona, brainstem
    from sentient.memory import architecture, gatekeeper
    from sentient.persona import identity_manager
    from sentient.brainstem import gateway as brainstem_gateway
    from sentient.brainstem.plugins import chat_output

    # Sleep, Health
    from sentient import sleep, health
    from sentient.sleep import scheduler
    from sentient.health import pulse_network, registry, innate_response

    # API, main
    from sentient import api
    from sentient.api import server
    from sentient import main

    # If we got here without exception, all packages loaded
    assert True


@pytest.mark.asyncio
async def test_memory_gatekeeper_logic():
    """Memory Gatekeeper makes sensible decisions without any LLM."""
    from sentient.memory.gatekeeper import MemoryGatekeeper

    gk = MemoryGatekeeper({
        "importance_threshold": 0.3,
        "semantic_dedup_similarity": 0.92,
        "recency_auto_pass_hours": 0,   # Turn off recency bypass for test
    })

    # Low importance → skip
    decision = gk.evaluate({
        "content": "trivial thing",
        "importance": 0.1,
        "created_at": 0,   # Old
    })
    assert decision.action == "skip"

    # High importance, no duplicates → store
    decision = gk.evaluate({
        "content": "important insight",
        "importance": 0.8,
        "created_at": 0,
    })
    assert decision.action == "store"

    # Exact hash duplicate → reinforce
    content_hash = gk._hash_content("important insight")
    decision = gk.evaluate(
        {"content": "important insight", "importance": 0.8, "created_at": 0},
        existing_by_hash={content_hash: {"id": "existing-id"}},
    )
    assert decision.action == "reinforce"
    assert decision.target_memory_id == "existing-id"


@pytest.mark.asyncio
async def test_envelope_through_heuristic_engine():
    """Heuristic engine classifies a creator message as Tier 2."""
    from sentient.thalamus.heuristic_engine import HeuristicEngine

    engine = HeuristicEngine({
        "tier1_keywords": ["emergency", "urgent"],
    })

    # Creator question → elevated
    env = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="How are you feeling today?",
    )
    assert engine.classify(env) == Priority.TIER_2_ELEVATED

    # Urgency keyword → Tier 1
    env_urgent = Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="this is urgent, please help",
    )
    assert engine.classify(env_urgent) == Priority.TIER_1_IMMEDIATE
