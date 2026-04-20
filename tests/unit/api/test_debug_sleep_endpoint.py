"""Unit tests for Phase 10 D4: Debug Sleep Endpoint."""
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sentient.api.server import APIServer
from sentient.sleep.scheduler import SleepStage
import asyncio


# Fixtures mirroring test_server_routes.py

@pytest.fixture
def mock_lifecycle():
    lifecycle = MagicMock()
    lifecycle.status_summary.return_value = {"phase": "running", "modules": ["memory", "cognitive_core"]}
    lifecycle.get_module.return_value = None
    return lifecycle


@pytest.fixture
def mock_chat_input():
    return AsyncMock()


@pytest.fixture
def mock_chat_output():
    chat_output = MagicMock()
    chat_output.outgoing_queue = asyncio.Queue()
    return chat_output


@pytest.fixture
def mock_health_network():
    health_network = MagicMock()
    health_network.snapshot.return_value = {}
    return health_network


@pytest.fixture
def mock_event_bus():
    return AsyncMock()


@pytest.fixture
def server(mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, mock_event_bus):
    config = {"host": "127.0.0.1", "port": 8765}
    return APIServer(config, mock_lifecycle, mock_chat_input, mock_chat_output, mock_health_network, event_bus=mock_event_bus)


@pytest.fixture
def client(server):
    return TestClient(server.app)


# Tests

def test_debug_sleep_returns_403_in_production(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle returns 403 when not in development mode."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "production"}):
        response = client.post("/api/debug/sleep_cycle", json={})
        assert response.status_code == 403
        assert "development" in response.json()["error"].lower()


def test_debug_sleep_returns_503_when_scheduler_missing(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle returns 503 if sleep scheduler unavailable."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "development"}):
        mock_lifecycle.get_module.return_value = None
        response = client.post("/api/debug/sleep_cycle", json={})
        assert response.status_code == 503


def test_debug_sleep_returns_409_when_already_sleeping(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle returns 409 if already in sleep."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "development"}):
        mock_scheduler = MagicMock()
        mock_scheduler.current_stage = SleepStage.SETTLING
        mock_lifecycle.get_module.side_effect = lambda name: mock_scheduler if name == "sleep_scheduler" else None
        response = client.post("/api/debug/sleep_cycle", json={})
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_debug_sleep_triggers_enter_sleep(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle calls scheduler.enter_sleep() in dev mode."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "development"}):
        mock_scheduler = MagicMock()
        mock_scheduler.current_stage = SleepStage.AWAKE
        mock_scheduler.enter_sleep = AsyncMock()
        mock_lifecycle.get_module.side_effect = lambda name: mock_scheduler if name == "sleep_scheduler" else None
        response = client.post("/api/debug/sleep_cycle", json={"requested_hours": 0.1})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sleep_entered"
        assert data["requested_hours"] == 0.1
        mock_scheduler.enter_sleep.assert_called_once_with(requested_hours=0.1)


def test_debug_sleep_clamps_requested_hours(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle clamps requested_hours to [0.01, 1.0]."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "development"}):
        mock_scheduler = MagicMock()
        mock_scheduler.current_stage = SleepStage.AWAKE
        mock_scheduler.enter_sleep = AsyncMock()
        mock_lifecycle.get_module.side_effect = lambda name: mock_scheduler if name == "sleep_scheduler" else None
        # Test upper clamp
        response = client.post("/api/debug/sleep_cycle", json={"requested_hours": 5.0})
        assert response.status_code == 200
        assert response.json()["requested_hours"] == 1.0


def test_debug_sleep_default_hours(client, mock_lifecycle):
    """POST /api/debug/sleep_cycle defaults to 0.1 hours."""
    with patch.dict(os.environ, {"SENTIENT_ENV": "development"}):
        mock_scheduler = MagicMock()
        mock_scheduler.current_stage = SleepStage.AWAKE
        mock_scheduler.enter_sleep = AsyncMock()
        mock_lifecycle.get_module.side_effect = lambda name: mock_scheduler if name == "sleep_scheduler" else None
        response = client.post("/api/debug/sleep_cycle", json={})
        assert response.status_code == 200
        assert response.json()["requested_hours"] == 0.1