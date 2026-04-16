"""Unit tests for event_bus.py.

Uses pytest + pytest-asyncio. No real I/O.
Covers: subscription, publication, wildcard, unsubscription,
no-subscriber events, error isolation, singleton, and event counting.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from sentient.core.event_bus import EventBus, get_event_bus, reset_event_bus


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


# ---------------------------------------------------------------------------
# 1. Subscription registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_registers_handler(bus: EventBus) -> None:
    """Subscribing a handler adds it to the subscriber list for that event."""
    handler = AsyncMock()

    await bus.subscribe("input.received", handler)

    assert handler in bus._subscribers["input.received"]


@pytest.mark.asyncio
async def test_subscribe_multiple_handlers_same_event(bus: EventBus) -> None:
    """Multiple handlers can subscribe to the same event type."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    await bus.subscribe("input.received", handler1)
    await bus.subscribe("input.received", handler2)

    assert len(bus._subscribers["input.received"]) == 2
    assert handler1 in bus._subscribers["input.received"]
    assert handler2 in bus._subscribers["input.received"]


@pytest.mark.asyncio
async def test_subscribe_wildcard(bus: EventBus) -> None:
    """Subscribing with '*' adds handler to wildcard list."""
    handler = AsyncMock()

    await bus.subscribe("*", handler)

    assert handler in bus._wildcard_subscribers
    assert "*" not in bus._subscribers  # wildcard doesn't pollute type-keyed dict


# ---------------------------------------------------------------------------
# 2. Event publication to single subscriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_to_single_subscriber(bus: EventBus) -> None:
    """Published event is received by the subscribed handler."""
    handler = AsyncMock()
    await bus.subscribe("test.event", handler)

    await bus.publish("test.event", {"key": "value"})

    # Allow fire-and-forget tasks to complete
    await asyncio.sleep(0.05)

    handler.assert_awaited_once()
    call_args = handler.call_args[0][0]
    assert call_args["event_type"] == "test.event"
    assert call_args["key"] == "value"
    assert "sequence" in call_args


@pytest.mark.asyncio
async def test_publish_includes_sequence_number(bus: EventBus) -> None:
    """Each published event gets an incrementing sequence number."""
    handler = AsyncMock()
    await bus.subscribe("seq.test", handler)

    await bus.publish("seq.test")
    await bus.publish("seq.test")

    await asyncio.sleep(0.05)

    assert handler.call_count == 2
    first_seq = handler.call_args_list[0][0][0]["sequence"]
    second_seq = handler.call_args_list[1][0][0]["sequence"]
    assert second_seq == first_seq + 1


@pytest.mark.asyncio
async def test_publish_with_no_payload(bus: EventBus) -> None:
    """Publishing without payload still includes event_type and sequence."""
    handler = AsyncMock()
    await bus.subscribe("empty.event", handler)

    await bus.publish("empty.event")

    await asyncio.sleep(0.05)

    call_args = handler.call_args[0][0]
    assert call_args["event_type"] == "empty.event"
    assert "sequence" in call_args
    # No extra keys beyond event_type and sequence
    assert len(call_args) == 2


# ---------------------------------------------------------------------------
# 3. Multiple subscribers same event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_to_multiple_subscribers(bus: EventBus) -> None:
    """All subscribers for an event type receive the event."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    await bus.subscribe("multi.event", handler1)
    await bus.subscribe("multi.event", handler2)

    await bus.publish("multi.event", {"data": "hello"})

    await asyncio.sleep(0.05)

    handler1.assert_awaited_once()
    handler2.assert_awaited_once()
    # Both receive the same payload
    assert handler1.call_args[0][0]["data"] == "hello"
    assert handler2.call_args[0][0]["data"] == "hello"


@pytest.mark.asyncio
async def test_wildcard_subscriber_receives_all_events(bus: EventBus) -> None:
    """Wildcard subscriber receives events of any type."""
    wildcard_handler = AsyncMock()

    await bus.subscribe("*", wildcard_handler)

    await bus.publish("input.received", {"x": 1})
    await bus.publish("cognitive.cycle.start", {"x": 2})
    await bus.publish("health.pulse", {"x": 3})

    await asyncio.sleep(0.05)

    assert wildcard_handler.call_count == 3


@pytest.mark.asyncio
async def test_specific_and_wildcard_both_receive(bus: EventBus) -> None:
    """An event triggers both specific subscribers and wildcard subscribers."""
    specific_handler = AsyncMock()
    wildcard_handler = AsyncMock()

    await bus.subscribe("test.event", specific_handler)
    await bus.subscribe("*", wildcard_handler)

    await bus.publish("test.event", {"msg": "hello"})

    await asyncio.sleep(0.05)

    specific_handler.assert_awaited_once()
    wildcard_handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. Unsubscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(bus: EventBus) -> None:
    """Unsubscribing removes the handler from the event type."""
    handler = AsyncMock()

    await bus.subscribe("test.event", handler)
    assert handler in bus._subscribers["test.event"]

    await bus.unsubscribe("test.event", handler)
    assert handler not in bus._subscribers["test.event"]


@pytest.mark.asyncio
async def test_unsubscribe_wildcard(bus: EventBus) -> None:
    """Unsubscribing from wildcard removes the handler."""
    handler = AsyncMock()

    await bus.subscribe("*", handler)
    assert handler in bus._wildcard_subscribers

    await bus.unsubscribe("*", handler)
    assert handler not in bus._wildcard_subscribers


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_handler_no_error(bus: EventBus) -> None:
    """Unsubscribing a handler that isn't subscribed doesn't raise."""
    handler = AsyncMock()
    # Should not raise
    await bus.unsubscribe("test.event", handler)


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_event_type_no_error(bus: EventBus) -> None:
    """Unsubscribing from an event type that has no subscribers doesn't raise."""
    handler = AsyncMock()
    await bus.unsubscribe("nonexistent.event", handler)


@pytest.mark.asyncio
async def test_unsubscribed_handler_does_not_receive_events(bus: EventBus) -> None:
    """After unsubscribing, handler no longer receives events."""
    handler = AsyncMock()

    await bus.subscribe("test.event", handler)
    await bus.unsubscribe("test.event", handler)

    await bus.publish("test.event", {"data": "should not receive"})

    await asyncio.sleep(0.05)

    handler.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Event types with no subscribers (no crash)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_no_crash(bus: EventBus) -> None:
    """Publishing an event with no subscribers doesn't raise."""
    # Should not raise or crash
    await bus.publish("unheard.event", {"data": "nobody listens"})
    # Event count should still increment
    assert bus.event_count() == 1


# ---------------------------------------------------------------------------
# 6. Error in one subscriber doesn't break others
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_in_handler_does_not_break_other_handlers(bus: EventBus) -> None:
    """If one handler raises, other handlers still receive the event."""
    good_handler = AsyncMock()

    async def bad_handler(payload: dict) -> None:
        raise ValueError("Handler error!")

    await bus.subscribe("test.event", bad_handler)
    await bus.subscribe("test.event", good_handler)

    await bus.publish("test.event", {"data": "important"})

    await asyncio.sleep(0.05)

    # Good handler should still be called
    good_handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_in_wildcard_does_not_break_specific_handler(
    bus: EventBus,
) -> None:
    """If a wildcard handler raises, specific handlers still receive the event."""
    good_handler = AsyncMock()

    async def bad_wildcard(payload: dict) -> None:
        raise RuntimeError("Wildcard error!")

    await bus.subscribe("*", bad_wildcard)
    await bus.subscribe("test.event", good_handler)

    await bus.publish("test.event", {"data": "payload"})

    await asyncio.sleep(0.05)

    good_handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. Async patterns — lock-based sequence numbering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_publishes_get_unique_sequences(bus: EventBus) -> None:
    """Concurrent publishes each get a unique sequence number."""
    handler = AsyncMock()
    await bus.subscribe("concurrent.test", handler)

    # Publish many events concurrently
    tasks = [bus.publish("concurrent.test", {"i": i}) for i in range(20)]
    await asyncio.gather(*tasks)

    await asyncio.sleep(0.1)

    assert handler.call_count == 20
    # Collect all sequence numbers
    sequences = [
        call[0][0]["sequence"] for call in handler.call_args_list
    ]
    # All sequence numbers should be unique
    assert len(set(sequences)) == 20


# ---------------------------------------------------------------------------
# 8. Singleton — get_event_bus / reset_event_bus
# ---------------------------------------------------------------------------


def test_get_event_bus_returns_singleton(reset_global_bus: None) -> None:
    """get_event_bus returns the same instance each time."""
    bus_a = get_event_bus()
    bus_b = get_event_bus()
    assert bus_a is bus_b


def test_reset_event_bus_creates_new_instance(reset_global_bus: None) -> None:
    """After reset, get_event_bus returns a new instance."""
    old_bus = get_event_bus()
    reset_event_bus()
    new_bus = get_event_bus()
    assert old_bus is not new_bus


# ---------------------------------------------------------------------------
# 9. Event count tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_count_increments(bus: EventBus) -> None:
    """event_count tracks total published events."""
    assert bus.event_count() == 0

    await bus.publish("test.event1")
    assert bus.event_count() == 1

    await bus.publish("test.event2")
    assert bus.event_count() == 2

    # Unheard events still count
    await bus.publish("nobody.listens")
    assert bus.event_count() == 3


@pytest.mark.asyncio
async def test_event_count_independent_of_subscriptions(bus: EventBus) -> None:
    """Event count increments even when no subscribers exist."""
    await bus.publish("nobody.listens")
    await bus.publish("still.nobody")

    assert bus.event_count() == 2


# ---------------------------------------------------------------------------
# 10. Payload merging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_merges_payload_with_event_metadata(bus: EventBus) -> None:
    """Published payload is merged with event_type and sequence."""
    handler = AsyncMock()
    await bus.subscribe("merge.test", handler)

    await bus.publish("merge.test", {"user": "akash", "priority": 1})

    await asyncio.sleep(0.05)

    payload = handler.call_args[0][0]
    assert payload["event_type"] == "merge.test"
    assert "sequence" in payload
    assert payload["user"] == "akash"
    assert payload["priority"] == 1