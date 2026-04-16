"""Unit tests for inference_gateway.py.

Uses pytest + pytest-asyncio + unittest.mock. No real API calls.
Covers: successful primary, primary failure with fallback, both failure,
cost tracking, endpoint metrics, provider string construction, timeout,
unknown model label, litellm unavailable, health pulse.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.core.inference_gateway import (
    InferenceGateway,
    InferenceRequest,
    _EndpointMetrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG: dict[str, Any] = {
    "models": {
        "cognitive-core": {
            "primary": {
                "provider": "anthropic",
                "model": "claude-opus-4-7",
                "max_tokens": 4096,
                "temperature": 0.7,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "qwen2.5:7b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
            ],
        },
        "world-model": {
            "primary": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "temperature": 0.3,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
            ],
        },
        "thalamus-classifier": {
            "primary": {
                "provider": "ollama",
                "model": "llama3.2:3b",
                "base_url": "http://localhost:11434",
                "max_tokens": 512,
                "temperature": 0.2,
            },
            "fallback": [
                {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 512,
                    "temperature": 0.2,
                },
            ],
        },
        "openai-test": {
            "primary": {
                "provider": "openai",
                "model": "gpt-4o",
                "max_tokens": 1024,
                "temperature": 0.5,
            },
            "fallback": [],
        },
    },
    "routing": {
        "fallback_on_error": True,
        "timeout_seconds": 60,
        "performance_tracking": {
            "enabled": True,
            "window_size_calls": 100,
            "health_threshold": 0.7,
        },
    },
    "cost_tracking": {
        "enabled": True,
        "log_path": "./data/logs/cost.log",
        "monthly_alert_usd": 200,
    },
}


def _make_gateway(config: dict | None = None) -> InferenceGateway:
    """Create a gateway with sample config (no litellm by default)."""
    cfg = config or SAMPLE_CONFIG
    gw = InferenceGateway(cfg)
    # Skip initialize (which tries to import litellm); set state manually
    gw._litellm = None  # Simulate litellm not installed for most tests
    return gw


def _mock_completion_response(
    text: str = "Hello",
    input_tokens: int = 10,
    output_tokens: int = 20,
    cost: float = 0.003,
) -> MagicMock:
    """Create a mock litellm completion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage.prompt_tokens = input_tokens
    response.usage.completion_tokens = output_tokens
    return response


# ---------------------------------------------------------------------------
# 1. Successful primary call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_primary_call() -> None:
    """When primary endpoint succeeds, return its response without fallback."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    mock_response = _mock_completion_response(text="Primary response")
    gw._litellm.acompletion = AsyncMock(return_value=mock_response)
    gw._litellm.completion_cost = MagicMock(return_value=0.005)

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="What is consciousness?",
        system_prompt="You are a sentient entity.",
    )
    response = await gw.infer(request)

    assert response.text == "Primary response"
    assert response.model_used == "claude-opus-4-7"
    assert response.provider == "anthropic"
    assert response.fallback_used is False
    assert response.error is None
    assert response.input_tokens == 10
    assert response.output_tokens == 20
    assert response.cost_usd == 0.005

    # Verify litellm was called with correct model string for anthropic
    call_args = gw._litellm.acompletion.call_args
    assert call_args.kwargs["model"] == "anthropic/claude-opus-4-7"
    assert call_args.kwargs["messages"][0]["role"] == "system"
    assert call_args.kwargs["messages"][1]["role"] == "user"
    assert call_args.kwargs["max_tokens"] == 4096
    assert call_args.kwargs["temperature"] == 0.7


# ---------------------------------------------------------------------------
# 2. Primary failure → fallback success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_primary_failure_fallback_success() -> None:
    """When primary fails, try fallback and return its response."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    # Primary fails, fallback succeeds
    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Primary endpoint down")
        return _mock_completion_response(text="Fallback response")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.001)

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="Test prompt",
    )
    response = await gw.infer(request)

    assert response.text == "Fallback response"
    assert response.model_used == "qwen2.5:7b"
    assert response.provider == "ollama"
    assert response.fallback_used is True
    assert response.error is None
    assert call_count == 2

    # Verify ollama model string includes api_base
    second_call_kwargs = gw._litellm.acompletion.call_args_list[1].kwargs
    assert second_call_kwargs["model"] == "ollama/qwen2.5:7b"
    assert second_call_kwargs["api_base"] == "http://localhost:11434"


# ---------------------------------------------------------------------------
# 3. Both failure → heuristic minimum return
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_endpoints_fail() -> None:
    """When all endpoints fail, return error response with last error."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(side_effect=RuntimeError("All down"))

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="Test prompt",
    )
    response = await gw.infer(request)

    assert response.text == ""
    assert response.model_used == "all_failed"
    assert response.provider == "none"
    assert response.fallback_used is True
    assert response.error is not None
    assert "All endpoints failed" in response.error
    assert response.latency_ms >= 0


# ---------------------------------------------------------------------------
# 4. Cost tracking accumulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_tracking_accumulation() -> None:
    """Cost accumulates across multiple calls."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    total_cost = 0.0
    costs = [0.01, 0.02, 0.005]

    for i, cost in enumerate(costs):

        async def mock_acompletion(**kwargs: Any) -> MagicMock:
            return _mock_completion_response(text=f"Response {i}")

        gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
        gw._litellm.completion_cost = MagicMock(return_value=cost)

        request = InferenceRequest(
            model_label="cognitive-core",
            prompt=f"Prompt {i}",
        )
        await gw.infer(request)
        total_cost += cost

    assert abs(gw._total_cost_usd - total_cost) < 0.001
    assert gw._call_count == 3


# ---------------------------------------------------------------------------
# 5. Endpoint metrics recording (success latency and failure)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_metrics_success() -> None:
    """Successful calls record success count and latency."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="OK")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.01)

    request = InferenceRequest(model_label="cognitive-core", prompt="Test")
    await gw.infer(request)

    # Check metrics
    key = "anthropic::claude-opus-4-7"
    assert key in gw._metrics
    assert gw._metrics[key].success_count == 1
    assert gw._metrics[key].failure_count == 0
    assert gw._metrics[key].total_latency_ms > 0


@pytest.mark.asyncio
async def test_endpoint_metrics_failure() -> None:
    """Failed calls record failure count."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(side_effect=RuntimeError("fail"))

    request = InferenceRequest(model_label="cognitive-core", prompt="Test")
    await gw.infer(request)

    # Primary endpoint should have a failure
    primary_key = "anthropic::claude-opus-4-7"
    assert primary_key in gw._metrics
    assert gw._metrics[primary_key].failure_count == 1
    assert gw._metrics[primary_key].success_count == 0

    # Fallback should also have a failure
    fallback_key = "ollama::qwen2.5:7b"
    assert fallback_key in gw._metrics
    assert gw._metrics[fallback_key].failure_count == 1


@pytest.mark.asyncio
async def test_endpoint_metrics_health_score() -> None:
    """Health score reflects recent success rate."""
    metrics = _EndpointMetrics()
    assert metrics.health_score() == 1.0  # Empty = perfect

    metrics.record_success(100.0)
    metrics.record_success(200.0)
    metrics.record_failure()
    assert metrics.health_score() == pytest.approx(2 / 3)

    # Fill to max (100 items)
    for _ in range(100):
        metrics.record_success(50.0)
    # Only recent 100 matter; all successes → score 1.0
    assert metrics.health_score() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 6. Provider string construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_string_anthropic() -> None:
    """Anthropic provider uses anthropic/ prefix in model string."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        return _mock_completion_response(text="test")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(model_label="cognitive-core", prompt="test")
    await gw.infer(request)

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["model"] == "anthropic/claude-opus-4-7"
    assert "api_base" not in call_kwargs


@pytest.mark.asyncio
async def test_provider_string_ollama() -> None:
    """Ollama provider uses ollama/ prefix and passes api_base."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    # Make primary fail so fallback (ollama) runs
    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Primary down")
        return _mock_completion_response(text="ollama response")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(model_label="cognitive-core", prompt="test")
    await gw.infer(request)

    # Second call should be to ollama
    fallback_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert fallback_kwargs["model"] == "ollama/qwen2.5:7b"
    assert fallback_kwargs["api_base"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_provider_string_openai() -> None:
    """OpenAI provider uses model name directly, no prefix."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="openai response")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(model_label="openai-test", prompt="test")
    await gw.infer(request)

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    # OpenAI: model string is just the model name, no prefix
    assert call_kwargs["model"] == "gpt-4o"
    assert "api_base" not in call_kwargs


# ---------------------------------------------------------------------------
# 7. Timeout handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_on_primary_fallback_succeeds() -> None:
    """When primary times out, fallback is tried."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        return _mock_completion_response(text="fallback after timeout")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.001)

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="test",
        timeout_seconds=5.0,
    )
    response = await gw.infer(request)

    assert response.text == "fallback after timeout"
    assert response.fallback_used is True

    # Primary endpoint should have a failure recorded
    primary_key = "anthropic::claude-opus-4-7"
    assert gw._metrics[primary_key].failure_count == 1


@pytest.mark.asyncio
async def test_timeout_all_endpoints() -> None:
    """When all endpoints time out, return error response."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(side_effect=asyncio.TimeoutError())

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="test",
        timeout_seconds=1.0,
    )
    response = await gw.infer(request)

    assert response.error is not None
    assert "All endpoints failed" in response.error


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_model_label() -> None:
    """Unknown model label returns error response."""
    gw = _make_gateway()

    request = InferenceRequest(
        model_label="nonexistent-model",
        prompt="test",
    )
    response = await gw.infer(request)

    assert response.text == ""
    assert response.model_used == "none"
    assert response.provider == "none"
    assert "Unknown model label" in response.error
    assert response.fallback_used is False


@pytest.mark.asyncio
async def test_litellm_not_installed() -> None:
    """When litellm is not installed, all endpoints fail gracefully."""
    gw = _make_gateway()
    # gw._litellm is None by default in _make_gateway

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="test",
    )
    response = await gw.infer(request)

    # All endpoints fail because litellm is None
    assert response.text == ""
    assert response.error is not None
    # Each endpoint should record a failure
    assert len(gw._metrics) >= 1


@pytest.mark.asyncio
async def test_request_overrides_config() -> None:
    """Request-level max_tokens and temperature override config defaults."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="custom")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="test",
        max_tokens=100,
        temperature=0.1,
    )
    await gw.infer(request)

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["max_tokens"] == 100
    assert call_kwargs["temperature"] == 0.1


@pytest.mark.asyncio
async def test_no_system_prompt() -> None:
    """When system_prompt is empty, messages list has only user message."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="no system")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="cognitive-core",
        prompt="just a prompt",
    )
    await gw.infer(request)

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "just a prompt"


@pytest.mark.asyncio
async def test_initialize_validates_models() -> None:
    """Initialize raises RuntimeError if no models configured."""
    gw = InferenceGateway({"models": {}})
    with pytest.raises(RuntimeError, match="No models configured"):
        await gw.initialize()


@pytest.mark.asyncio
async def test_initialize_validates_primary() -> None:
    """Initialize raises RuntimeError if model missing primary config."""
    gw = InferenceGateway({"models": {"test": {"fallback": []}}})
    with pytest.raises(RuntimeError, match="missing 'primary'"):
        await gw.initialize()


@pytest.mark.asyncio
async def test_health_pulse() -> None:
    """Health pulse includes total calls and cost."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="ok")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.01)

    request = InferenceRequest(model_label="cognitive-core", prompt="test")
    await gw.infer(request)

    pulse = gw.health_pulse()
    assert pulse.module_name == "inference_gateway"
    assert pulse.metrics["total_calls"] == 1
    assert pulse.metrics["total_cost_usd"] > 0
    assert "endpoints" in pulse.metrics
    assert "anthropic::claude-opus-4-7" in pulse.metrics["endpoints"]


@pytest.mark.asyncio
async def test_shutdown_logs_cost() -> None:
    """Shutdown completes without error and logs final cost."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._call_count = 5
    gw._total_cost_usd = 1.23

    # Should not raise
    await gw.shutdown()


@pytest.mark.asyncio
async def test_metrics_latency_tracking() -> None:
    """Metrics track total latency across calls."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    gw._litellm.acompletion = AsyncMock(
        return_value=_mock_completion_response(text="ok")
    )
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    # Make two calls
    for _ in range(2):
        request = InferenceRequest(model_label="cognitive-core", prompt="test")
        await gw.infer(request)

    key = "anthropic::claude-opus-4-7"
    assert gw._metrics[key].success_count == 2
    assert gw._metrics[key].total_latency_ms > 0


@pytest.mark.asyncio
async def test_fallback_without_fallback_config() -> None:
    """Model with no fallback list returns error when primary fails."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(side_effect=RuntimeError("fail"))

    request = InferenceRequest(model_label="openai-test", prompt="test")
    response = await gw.infer(request)

    assert response.text == ""
    assert response.error is not None
    assert "All endpoints failed" in response.error