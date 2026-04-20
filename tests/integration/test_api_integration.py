"""Integration tests for the rebuilt APIServer with real EventBus."""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sentient.api.server import APIServer
from sentient.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_event_bus():
    """Real EventBus instance for integration tests."""
    bus = EventBus()
    yield bus
    # No reset needed — using fresh instance per test


@pytest.fixture
def mock_lifecycle():
    """Lifecycle manager with status_summary and get_module."""
    lifecycle = MagicMock()
    lifecycle.status_summary.return_value = {"phase": "running", "modules": {}}
    lifecycle.get_module.return_value = None
    return lifecycle


@pytest.fixture
def mock_chat_input():
    """Chat input plugin with async inject method."""
    chat_input = AsyncMock()
    return chat_input


@pytest.fixture
def mock_chat_output():
    """Chat output plugin with outgoing_queue."""
    chat_output = MagicMock()
    chat_output.outgoing_queue = asyncio.Queue()
    return chat_output


@pytest.fixture
def mock_health_network():
    """Health pulse network with snapshot."""
    health_network = MagicMock()
    health_network.snapshot.return_value = {
        "thalamus": {"latest": {"status": "healthy"}, "pulse_count": 1, "status": "healthy"},
    }
    return health_network


@pytest.fixture
def server(mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, real_event_bus):
    """Construct APIServer with real EventBus."""
    config = {"host": "127.0.0.1", "port": 8765}
    return APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=real_event_bus,
    )


@pytest.fixture
def client(server):
    """TestClient attached to the server app."""
    return TestClient(server.app)


# ---------------------------------------------------------------------------
# Real event bus — event broadcasting via WS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_bus_publish_broadcasts_to_ws_client(server, real_event_bus):
    """Publishing an event on the real EventBus broadcasts to connected WS client."""
    # Mock a WebSocket client
    mock_ws = AsyncMock()
    server._ws_clients.add(mock_ws)

    # Subscribe server to event bus (normally happens in start())
    await server.event_bus.subscribe("*", server._broadcast_event)

    # Publish an event via the real event bus
    await server.event_bus.publish("cognitive.cycle.complete", {"turn_id": "test-123"})

    # Give the async handler time to run
    await asyncio.sleep(0.05)

    # Client should receive the event (server uses send_text, not send_json)
    mock_ws.send_text.assert_called_once()
    data = json.loads(mock_ws.send_text.call_args[0][0])
    assert data["type"] == "event"
    assert data["event_name"] == "cognitive.cycle.complete"
    assert data["turn_id"] == "test-123"
    assert data["stage"] == "cognitive_core"


@pytest.mark.asyncio
async def test_multiple_events_all_broadcast_to_ws_client(server, real_event_bus):
    """Multiple events published consecutively all reach the WS client."""
    # Mock a WebSocket client
    mock_ws = AsyncMock()
    server._ws_clients.add(mock_ws)

    # Subscribe server to event bus
    await server.event_bus.subscribe("*", server._broadcast_event)

    # Publish several events
    events_to_send = [
        ("input.received", {"text": "hello"}),
        ("checkpost.tagged", {}),
        ("tlp.enriched", {}),
    ]
    for event_type, payload in events_to_send:
        await server.event_bus.publish(event_type, payload)

    # Give handlers time to complete
    await asyncio.sleep(0.1)

    assert mock_ws.send_text.call_count == len(events_to_send)
    received_names = [json.loads(call[0][0])["event_name"] for call in mock_ws.send_text.call_args_list]
    for event_type, _ in events_to_send:
        assert event_type in received_names


# ---------------------------------------------------------------------------
# POST /api/chat → event → pipeline → turn record
# ---------------------------------------------------------------------------


def test_post_chat_flow_integration(client, server, real_event_bus, mock_chat_input):
    """POST /api/chat creates turn record, fires event, injects into chat_input."""
    # Verify pre-state
    assert len(server._turn_records) == 0

    response = client.post("/api/chat", json={"message": "integration test"})
    assert response.status_code == 202
    turn_id = response.json()["turn_id"]

    # Turn record should exist
    assert turn_id in server._turn_records
    record = server._turn_records[turn_id]
    assert record.user_message == "integration test"
    assert record.is_complete is False

    # chat_input.inject was called
    mock_chat_input.inject.assert_called_once()

    # Event was published
    assert real_event_bus.event_count() >= 1


@pytest.mark.asyncio
async def test_post_chat_turn_record_updated_after_drain(client, server, mock_chat_output):
    """Turn record is updated when ChatOutputPlugin delivers a reply."""
    # Create a turn via POST
    response = client.post("/api/chat", json={"message": "test"})
    turn_id = response.json()["turn_id"]

    # Simulate a reply arriving via outgoing queue
    reply_message = {
        "type": "chat_message",
        "text": "assistant response",
        "turn_id": turn_id,
        "timestamp": time.time(),
    }
    await mock_chat_output.outgoing_queue.put(reply_message)

    # Mock a WebSocket client so drain doesn't fail
    mock_ws = AsyncMock()
    server._ws_clients.add(mock_ws)

    # Run drain briefly
    drain_task = asyncio.create_task(server._drain_outgoing())
    await asyncio.sleep(0.05)
    drain_task.cancel()
    try:
        await drain_task
    except asyncio.CancelledError:
        pass

    # Turn record should be complete
    record = server._turn_records[turn_id]
    assert record.is_complete is True
    assert record.assistant_reply == "assistant response"
    assert record.completed_at is not None


# ---------------------------------------------------------------------------
# GET /api/events/recent after events
# ---------------------------------------------------------------------------


def test_get_recent_events_returns_broadcasted_events(client, server, real_event_bus):
    """GET /api/events/recent returns events stored in ring buffer after broadcasting."""
    # Pre-populate via broadcast
    asyncio.run(server._broadcast_event({
        "event_type": "memory.candidate",
        "sequence": 1,
        "timestamp": time.time(),
    }))

    response = client.get("/api/events/recent")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 1
    event_names = [e["event_name"] for e in events]
    assert "memory.candidate" in event_names


# ---------------------------------------------------------------------------
# Health snapshot on WS connect includes all modules
# ---------------------------------------------------------------------------


def test_ws_health_snapshot_includes_module_data(client, mock_health_network):
    """Health snapshot sent on WS connect contains module status data."""
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "health"
        assert "thalamus" in data["data"]
        assert data["data"]["thalamus"]["status"] == "healthy"