"""Integration smoke tests for the rebuilt APIServer.

Tests the full request-response cycle for REST endpoints and
isolated WebSocket message handling, using step-wise verification
instead of full async WebSocket lifecycles.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sentient.api.server import APIServer, TurnRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_lifecycle():
    """Lifecycle manager with status_summary and get_module."""
    lifecycle = MagicMock()
    lifecycle.status_summary.return_value = {
        "phase": "running",
        "status": "active",
        "modules": ["memory", "cognitive_core"],
    }
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
def mock_event_bus():
    """Mock event bus with async subscribe/publish."""
    bus = AsyncMock()
    return bus


@pytest.fixture
def server(mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus):
    """Construct APIServer with all mocks."""
    config = {"host": "127.0.0.1", "port": 8765, "static_dir": "static"}
    return APIServer(
        config,
        mock_lifecycle,
        mock_chat_input,
        mock_chat_output,
        mock_health_network,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def client(server):
    """TestClient attached to the server app."""
    return TestClient(server.app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_root_returns_html(client):
    """GET / returns HTML with 'Sentient' in the body."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Sentient" in response.text


def test_health_endpoint_returns_snapshot(client, mock_health_network):
    """GET /api/health returns health_network.snapshot()."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == mock_health_network.snapshot.return_value


def test_status_endpoint_returns_summary(client, mock_lifecycle):
    """GET /api/status returns lifecycle.status_summary()."""
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == mock_lifecycle.status_summary.return_value


def test_chat_post_accepts_message(client):
    """POST /api/chat with {'message': 'hello'} returns 202 with turn_id."""
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 202
    data = response.json()
    assert "turn_id" in data
    assert data["status"] == "accepted"


def test_chat_post_rejects_empty_message(client):
    """POST /api/chat with {'message': ''} returns 400."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400
    assert "error" in response.json()


def test_chat_post_rejects_missing_message(client):
    """POST /api/chat with {} returns 400."""
    response = client.post("/api/chat", json={})
    assert response.status_code == 400


def test_chat_post_creates_turn_record(client, server):
    """After POST /api/chat, turn_id appears in server._turn_records."""
    response = client.post("/api/chat", json={"message": "hello"})
    turn_id = response.json()["turn_id"]
    assert turn_id in server._turn_records
    assert server._turn_records[turn_id].user_message == "hello"


def test_chat_post_preserves_session_id(client, mock_chat_input):
    """POST /api/chat with session_id='custom-session' passes it through to inject."""
    client.post("/api/chat", json={"message": "hello", "session_id": "custom-session"})
    mock_chat_input.inject.assert_called_once()
    payload = mock_chat_input.inject.call_args[0][0]
    assert payload["session_id"] == "custom-session"


def test_chat_post_publishes_event(client, mock_event_bus):
    """After POST /api/chat, event_bus.publish is called."""
    client.post("/api/chat", json={"message": "hello"})
    mock_event_bus.publish.assert_called_once()
    args = mock_event_bus.publish.call_args[0]
    assert args[0] == "chat.input.received"
    assert args[1]["text"] == "hello"


def test_events_recent_returns_list(client):
    """GET /api/events/recent returns a list (empty initially)."""
    response = client.get("/api/events/recent")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_events_recent_returns_broadcast_events(client, server):
    """After _broadcast_event, GET /api/events/recent includes the event."""
    event_payload = {"event_type": "test.event", "data": "test"}
    await server._broadcast_event(event_payload)

    response = client.get("/api/events/recent")
    events = response.json()
    assert len(events) >= 1
    assert events[-1]["event_name"] == "test.event"


def test_turns_endpoint_returns_record(client, server):
    """After creating a turn, GET /api/turns/{turn_id} returns it."""
    turn_id = "test-turn-id"
    server._turn_records[turn_id] = TurnRecord(turn_id, "hello", time.time())

    response = client.get(f"/api/turns/{turn_id}")
    assert response.status_code == 200
    assert response.json()["turn_id"] == turn_id
    assert response.json()["user_message"] == "hello"


def test_turns_endpoint_returns_404_for_unknown(client):
    """GET /api/turns/nonexistent returns 404."""
    response = client.get("/api/turns/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_handle_ws_message_ping(server):
    """_handle_ws_message({'type': 'ping'}, ts) returns {'type': 'pong', 'timestamp': ts}."""
    ts = time.time()
    result = await server._handle_ws_message({"type": "ping"}, ts)
    assert result == {"type": "pong", "timestamp": ts}


@pytest.mark.asyncio
async def test_handle_ws_message_chat(server, mock_chat_input):
    """_handle_ws_message({'type': 'chat', 'text': 'hello', 'session_id': 'main'}, ts) calls chat_input.inject."""
    ts = time.time()
    await server._handle_ws_message({"type": "chat", "text": "hello", "session_id": "main"}, ts)
    mock_chat_input.inject.assert_called_once()
    payload = mock_chat_input.inject.call_args[0][0]
    assert payload["text"] == "hello"
    assert payload["session_id"] == "main"


@pytest.mark.asyncio
async def test_handle_ws_message_ignores_empty_chat(server, mock_chat_input):
    """_handle_ws_message({'type': 'chat', 'text': ''}, ts) does NOT call inject."""
    await server._handle_ws_message({"type": "chat", "text": ""}, time.time())
    mock_chat_input.inject.assert_not_called()


@pytest.mark.asyncio
async def test_handle_ws_message_returns_none_for_unknown(server):
    """_handle_ws_message({'type': 'unknown'}, ts) returns None."""
    result = await server._handle_ws_message({"type": "unknown"}, time.time())
    assert result is None


@pytest.mark.parametrize("event_type,expected_stage", [
    ("thalamus.event", "thalamus"),
    ("cognitive.event", "cognitive_core"),
    ("memory.event", "memory"),
    ("random.event", "system"),
])
@pytest.mark.asyncio
async def test_broadcast_event_maps_stages(server, event_type, expected_stage):
    """_broadcast_event with different event_type prefixes maps to correct stages."""
    await server._broadcast_event({"event_type": event_type})
    event = server._event_buffer[-1]
    assert event["stage"] == expected_stage


@pytest.mark.asyncio
async def test_ring_buffer_max_size(server):
    """Adding >50 events truncates to latest 50."""
    for i in range(60):
        await server._broadcast_event({"event_type": f"test.{i}"})

    assert len(server._event_buffer) == 50
    assert server._event_buffer[0]["event_name"] == "test.10"
    assert server._event_buffer[-1]["event_name"] == "test.59"


def test_memory_count_endpoint(client, mock_lifecycle):
    """GET /api/memory/count when memory module available."""
    mock_memory = MagicMock()
    mock_memory.health_pulse.return_value.metrics = {"count": 100}
    mock_lifecycle.get_module.side_effect = lambda name: mock_memory if name == "memory" else None

    response = client.get("/api/memory/count")
    assert response.status_code == 200
    assert response.json() == {"count": 100}


def test_cognitive_recent_endpoint(client, mock_lifecycle):
    """GET /api/cognitive/recent when cognitive_core available."""
    mock_cognitive = MagicMock()
    mock_cognitive.health_pulse.return_value.metrics = {"recent": []}
    mock_lifecycle.get_module.side_effect = lambda name: mock_cognitive if name == "cognitive_core" else None

    response = client.get("/api/cognitive/recent")
    assert response.status_code == 200
    assert response.json() == {"recent": []}


def test_static_file_not_found(client):
    """GET /api/static/nonexistent returns 404."""
    response = client.get("/static/nonexistent.txt")
    assert response.status_code == 404
