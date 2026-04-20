"""Unit tests for Inference Gateway telemetry features (Phase 9 D8)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.core.event_bus import EventBus
from sentient.core.inference_gateway import (
    InferenceGateway,
    InferenceRequest,
    InferenceResponse,
)


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus that tracks published events."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def gateway_config():
    """Minimal gateway config for testing."""
    return {
        "models": {
            "test-model": {
                "primary": {
                    "provider": "anthropic",
                    "model": "claude-3-haiku",
                    "max_tokens": 100,
                },
                "fallback": [
                    {
                        "provider": "ollama",
                        "model": "llama3",
                        "base_url": "http://localhost:11434",
                    },
                ],
            },
            "fast-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3",
                    "base_url": "http://localhost:11434",
                },
            },
        },
        "routing": {},
        "cost_tracking": {},
    }


@pytest.fixture
def gateway(gateway_config, mock_event_bus):
    """Create a gateway instance with mock event bus."""
    gw = InferenceGateway(gateway_config, event_bus=mock_event_bus)
    return gw


class TestInferPublishesCallStartedEvent:
    """Test that infer() publishes inference.call.started before trying endpoints."""

    @pytest.mark.asyncio
    async def test_infer_publishes_call_started_event(self, gateway, mock_event_bus):
        """Verify inference.call.started is published before trying endpoints."""
        request = InferenceRequest(model_label="test-model", prompt="hello")

        # Mock _try_endpoint to return a successful response
        response = InferenceResponse(
            text="hello back",
            model_used="claude-3-haiku",
            provider="anthropic",
            fallback_used=False,
            latency_ms=100.0,
        )
        with patch.object(gateway, "_try_endpoint", new_callable=AsyncMock) as mock_try:
            mock_try.return_value = response
            await gateway.infer(request)

        # Verify call.started was published
        mock_event_bus.publish.assert_any_call(
            "inference.call.started",
            {
                "model_label": "test-model",
                "primary_endpoint": "anthropic/claude-3-haiku",
                "fallback_count": 1,
            },
        )

        # Verify it was called BEFORE _try_endpoint
        calls = mock_event_bus.publish.call_args_list
        started_call = next(
            c for c in calls if c[0][0] == "inference.call.started"
        )
        # Should be the first publish call
        assert calls.index(started_call) == 0


class TestInferPublishesCallCompleteOnSuccess:
    """Test that infer() publishes inference.call.complete on success."""

    @pytest.mark.asyncio
    async def test_infer_publishes_call_complete_on_success(self, gateway, mock_event_bus):
        """Verify inference.call.complete is published when call succeeds."""
        request = InferenceRequest(
            model_label="test-model",
            prompt="hello",
        )
        response = InferenceResponse(
            text="response text",
            model_used="claude-3-haiku",
            provider="anthropic",
            fallback_used=False,
            latency_ms=150.5,
            input_tokens=10,
            output_tokens=25,
            cost_usd=0.001,
        )
        with patch.object(gateway, "_try_endpoint", new_callable=AsyncMock) as mock_try:
            mock_try.return_value = response
            await gateway.infer(request)

        mock_event_bus.publish.assert_any_call(
            "inference.call.complete",
            {
                "model_label": "test-model",
                "model_actual": "claude-3-haiku",
                "provider": "anthropic",
                "duration_ms": 150.5,
                "tokens_in": 10,
                "tokens_out": 25,
                "cost_usd": 0.001,
                "fallback_used": False,
            },
        )


class TestInferPublishesCallFailedOnAllFail:
    """Test that infer() publishes inference.call.failed when all endpoints fail."""

    @pytest.mark.asyncio
    async def test_infer_publishes_call_failed_on_all_fail(self, gateway, mock_event_bus):
        """Verify inference.call.failed is published when all endpoints fail."""
        request = InferenceRequest(model_label="test-model", prompt="hello")

        # Mock _try_endpoint to return error responses
        error_response = InferenceResponse(
            text="",
            model_used="claude-3-haiku",
            provider="anthropic",
            fallback_used=False,
            latency_ms=50.0,
            error="connection refused",
        )
        with patch.object(gateway, "_try_endpoint", new_callable=AsyncMock) as mock_try:
            mock_try.return_value = error_response
            await gateway.infer(request)

        mock_event_bus.publish.assert_any_call(
            "inference.call.failed",
            {
                "model_label": "test-model",
                "error": "connection refused",
            },
        )


class TestFallbackTriggeredPublishesEvent:
    """Test that inference.fallback.triggered is published when fallback succeeds."""

    @pytest.mark.asyncio
    async def test_fallback_triggered_publishes_event(self, gateway, mock_event_bus):
        """Verify inference.fallback.triggered is published when fallback succeeds."""
        # Call _try_endpoint directly to test the fallback event
        # (the event is published inside _try_endpoint, not infer())
        request = InferenceRequest(
            model_label="test-model",
            prompt="hello",
        )
        fallback_endpoint = {
            "provider": "ollama",
            "model": "llama3",
            "base_url": "http://localhost:11434",
        }

        # Mock litellm so the actual code path runs
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "fallback response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 50

        gateway._litellm = MagicMock()
        gateway._litellm.acompletion = AsyncMock(return_value=mock_response)
        gateway._litellm.completion_cost = MagicMock(return_value=0.0)

        # is_fallback=True should trigger the event
        result = await gateway._try_endpoint(request, fallback_endpoint, is_fallback=True)

        assert result.error is None
        assert result.fallback_used is True
        mock_event_bus.publish.assert_any_call(
            "inference.fallback.triggered",
            {
                "model_label": "test-model",
                "model_actual": "llama3",
                "provider": "ollama",
                "duration_ms": result.latency_ms,
                "tokens_in": 10,
                "tokens_out": 50,
                "cost_usd": 0.0,
            },
        )


class TestGetStatusReturnsEndpointMetrics:
    """Test that get_status() returns expected endpoint metrics structure."""

    def test_get_status_returns_endpoint_metrics(self, gateway):
        """Verify status dict contains expected keys and endpoint data."""
        # Manually add some metrics
        gateway._metrics["anthropic::claude-3-haiku"] = MagicMock(
            success_count=5,
            failure_count=1,
            total_latency_ms=500.0,
            health_score=MagicMock(return_value=0.833),
        )
        gateway._call_count = 6
        gateway._total_cost_usd = 0.05

        status = gateway.get_status()

        assert "total_calls" in status
        assert "total_cost_usd" in status
        assert "endpoints" in status
        assert status["total_calls"] == 6
        assert status["total_cost_usd"] == 0.05
        assert "anthropic::claude-3-haiku" in status["endpoints"]


class TestGetRecentCallsReturnsRingBuffer:
    """Test that get_recent_calls() returns calls from ring buffer."""

    def test_get_recent_calls_returns_ring_buffer(self, gateway):
        """Verify recent calls are returned with full metadata."""
        # Add some calls to the ring buffer
        gateway._recent_calls.append(
            {
                "timestamp": 1000.0,
                "model_label": "test-model",
                "model_actual": "claude-3-haiku",
                "provider": "anthropic",
                "fallback_used": False,
                "duration_ms": 100.0,
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_usd": 0.001,
                "error": None,
            }
        )
        gateway._recent_calls.append(
            {
                "timestamp": 1001.0,
                "model_label": "test-model",
                "model_actual": "llama3",
                "provider": "ollama",
                "fallback_used": True,
                "duration_ms": 200.0,
                "tokens_in": 10,
                "tokens_out": 40,
                "cost_usd": 0.0,
                "error": None,
            }
        )

        recent = gateway.get_recent_calls()

        assert len(recent) == 2
        assert recent[0]["model_actual"] == "claude-3-haiku"
        assert recent[1]["model_actual"] == "llama3"

    def test_recent_calls_respects_limit(self, gateway):
        """Verify limit parameter limits the number of returned calls."""
        # Add 5 calls
        for i in range(5):
            gateway._recent_calls.append(
                {
                    "timestamp": 1000.0 + i,
                    "model_label": f"model-{i}",
                    "model_actual": f"actual-{i}",
                    "provider": "test",
                    "fallback_used": False,
                    "duration_ms": 100.0,
                    "tokens_in": 10,
                    "tokens_out": 20,
                    "cost_usd": 0.001,
                    "error": None,
                }
            )

        # Request only last 3
        recent = gateway.get_recent_calls(limit=3)

        assert len(recent) == 3
        assert recent[0]["model_actual"] == "actual-2"
        assert recent[1]["model_actual"] == "actual-3"
        assert recent[2]["model_actual"] == "actual-4"


class TestRecentCallsRingBufferOverflow:
    """Test that the ring buffer properly overflows."""

    def test_ring_buffer_maxlen_200(self, gateway):
        """Verify ring buffer is capped at 200 entries."""
        # Add 205 entries
        for i in range(205):
            gateway._recent_calls.append(
                {
                    "timestamp": 1000.0 + i,
                    "model_label": f"model-{i}",
                    "model_actual": f"actual-{i}",
                    "provider": "test",
                    "fallback_used": False,
                    "duration_ms": 100.0,
                    "tokens_in": 10,
                    "tokens_out": 20,
                    "cost_usd": 0.001,
                    "error": None,
                }
            )

        # Should only have 200
        assert len(gateway._recent_calls) == 200
        # First entry should be the oldest of the last 200 (i.e., index 5)
        assert gateway._recent_calls[0]["model_actual"] == "actual-5"


class TestEventBusParameterOptional:
    """Test that event_bus parameter is optional and defaults to global bus."""

    def test_event_bus_defaults_to_global(self, gateway_config):
        """Verify event_bus defaults to get_event_bus() when not provided."""
        with patch("sentient.core.inference_gateway.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            gw = InferenceGateway(gateway_config)
            mock_get_bus.assert_called_once()
            assert gw.event_bus is mock_get_bus.return_value

    def test_event_bus_can_be_passed_explicitly(self, gateway_config, mock_event_bus):
        """Verify explicit event_bus parameter is used."""
        gw = InferenceGateway(gateway_config, event_bus=mock_event_bus)
        assert gw.event_bus is mock_event_bus
