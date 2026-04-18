"""Unit tests for event bus serialization of complex objects.

Tests that EventBus.publish() produces JSON-serializable payloads when
dataclass objects (Envelope, ReviewVerdict) are in the payload, verifying
both the source-side sanitization layer.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from enum import Enum

import pytest

from sentient.core.event_bus import EventBus, reset_event_bus
from sentient.core.envelope import Envelope, Priority, SourceType, TrustLevel
from sentient.prajna.frontal.world_model import ReviewVerdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus() -> EventBus:
    """Fresh EventBus instance for each test."""
    return EventBus()


@pytest.fixture
def reset_global_bus() -> None:
    """Reset the global singleton before and after each test."""
    reset_event_bus()
    yield
    reset_event_bus()


class _TestPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# 1. Bare Envelope in payload data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_bare_envelope(bus: EventBus) -> None:
    """Publish event with bare Envelope — subscriber receives JSON-serializable dict."""
    received_payload = None

    async def handler(payload: dict) -> None:
        nonlocal received_payload
        received_payload = payload

    await bus.subscribe("test.envelope.bare", handler)

    envelope = Envelope(
        envelope_id="test-env-001",
        source_type=SourceType.CHAT,
        plugin_name="test_plugin",
        processed_content="hello world",
        priority=Priority.TIER_1_IMMEDIATE,
    )

    await bus.publish("test.envelope.bare", {"envelope": envelope})
    await asyncio.sleep(0.05)

    assert received_payload is not None
    # Verify it's JSON-serializable
    json_dumped = json.dumps(received_payload)
    assert json_dumped is not None

    parsed = json.loads(json_dumped)
    assert "envelope" in parsed
    assert parsed["envelope"]["envelope_id"] == "test-env-001"
    assert parsed["envelope"]["source_type"] == "chat"


# ---------------------------------------------------------------------------
# 2. Envelope as dict value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_envelope_in_dict_value(bus: EventBus) -> None:
    """Publish event with Envelope nested as dict value — subscriber receives JSON-serializable dict."""
    received_payload = None

    async def handler(payload: dict) -> None:
        nonlocal received_payload
        received_payload = payload

    await bus.subscribe("test.envelope.in_dict", handler)

    envelope = Envelope(
        envelope_id="test-env-002",
        source_type=SourceType.VOICE,
        plugin_name="voice_plugin",
        trust_level=TrustLevel.TIER_2_TRUSTED,
        metadata={"key": "value"},
    )

    await bus.publish("test.envelope.in_dict", {
        "event_name": "test",
        "source": envelope,
    })
    await asyncio.sleep(0.05)

    assert received_payload is not None
    json_dumped = json.dumps(received_payload)
    parsed = json.loads(json_dumped)
    assert parsed["source"]["envelope_id"] == "test-env-002"
    assert parsed["source"]["source_type"] == "voice"
    assert parsed["source"]["trust_level"] == 2  # TIER_2_TRUSTED value


# ---------------------------------------------------------------------------
# 3. List of Envelopes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_list_of_envelopes(bus: EventBus) -> None:
    """Publish event with list of Envelopes — subscriber receives JSON-serializable list."""
    received_payload = None

    async def handler(payload: dict) -> None:
        nonlocal received_payload
        received_payload = payload

    await bus.subscribe("test.envelope.list", handler)

    envelopes = [
        Envelope(envelope_id="env-list-001", source_type=SourceType.CHAT),
        Envelope(envelope_id="env-list-002", source_type=SourceType.FILE_SYSTEM),
    ]

    await bus.publish("test.envelope.list", {"envelopes": envelopes})
    await asyncio.sleep(0.05)

    assert received_payload is not None
    json_dumped = json.dumps(received_payload)
    parsed = json.loads(json_dumped)

    assert len(parsed["envelopes"]) == 2
    assert parsed["envelopes"][0]["envelope_id"] == "env-list-001"
    assert parsed["envelopes"][1]["envelope_id"] == "env-list-002"


# ---------------------------------------------------------------------------
# 4. ReviewVerdict dataclass in payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_review_verdict(bus: EventBus) -> None:
    """Publish event with ReviewVerdict dataclass — subscriber receives JSON-serializable dict."""
    received_payload = None

    async def handler(payload: dict) -> None:
        nonlocal received_payload
        received_payload = payload

    await bus.subscribe("test.verdict", handler)

    verdict = ReviewVerdict(
        cycle_id="cycle-42",
        decision={"type": "respond", "text": "hello"},
        verdict="approved",
        dimension_assessments={
            "feasibility": {"score": 0.9, "notes": "possible"},
            "ethics": {"score": 1.0, "notes": "aligned"},
        },
        advisory_notes="Proceed normally.",
        confidence=0.95,
        revision_count=0,
    )

    await bus.publish("test.verdict", {"verdict": verdict})
    await asyncio.sleep(0.05)

    assert received_payload is not None
    json_dumped = json.dumps(received_payload)
    parsed = json.loads(json_dumped)

    assert parsed["verdict"]["cycle_id"] == "cycle-42"
    assert parsed["verdict"]["verdict"] == "approved"
    assert parsed["verdict"]["confidence"] == 0.95
    assert parsed["verdict"]["dimension_assessments"]["feasibility"]["score"] == 0.9


# ---------------------------------------------------------------------------
# 5. Nested structure: datetime, Enum, set, and Envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_nested_datetime_enum_set_envelope(bus: EventBus) -> None:
    """Publish event with nested dict containing datetime, Enum, set, and Envelope."""
    received_payload = None

    async def handler(payload: dict) -> None:
        nonlocal received_payload
        received_payload = payload

    await bus.subscribe("test.nested", handler)

    envelope = Envelope(
        envelope_id="nested-env-001",
        source_type=SourceType.CALENDAR,
        plugin_name="calendar_plugin",
        entity_tags=["meeting", "deadline"],
        topic_tags=["work"],
        emotional_tags={"anticipation": 0.7, "stress": 0.3},
    )

    nested_data = {
        "timestamp": datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "priority_level": _TestPriority.HIGH,
        "unique_ids": {"id-1", "id-2", "id-3"},
        "origin": envelope,
        "metadata": {
            "created": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "status": _TestPriority.MEDIUM,
            "flags": {"flag-a", "flag-b"},
        },
    }

    await bus.publish("test.nested", {"data": nested_data})
    await asyncio.sleep(0.05)

    assert received_payload is not None
    json_dumped = json.dumps(received_payload)
    parsed = json.loads(json_dumped)

    # datetime → ISO string
    assert "2025-01-15T10:30:00" in json_dumped
    # Enum → value
    assert parsed["data"]["priority_level"] == "high"
    # set → list
    assert isinstance(parsed["data"]["unique_ids"], list)
    assert set(parsed["data"]["unique_ids"]) == {"id-1", "id-2", "id-3"}
    # Envelope → dict
    assert parsed["data"]["origin"]["envelope_id"] == "nested-env-001"
    assert parsed["data"]["origin"]["source_type"] == "calendar"
    # nested metadata
    assert parsed["data"]["metadata"]["status"] == "medium"
    assert isinstance(parsed["data"]["metadata"]["flags"], list)