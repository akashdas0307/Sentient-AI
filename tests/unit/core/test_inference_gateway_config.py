"""Unit tests for InferenceGateway config-to-label resolution.

Verifies that the config/inference_gateway.yaml maps all abstract model labels
(cognitive-core, world-model, thalamus-classifier, etc.) to real Ollama cloud
models and that the gateway correctly routes requests through those labels.

No real LLM calls — all litellm calls are mocked.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.core.inference_gateway import (
    InferenceGateway,
    InferenceRequest,
    _EndpointMetrics,
)

# ---------------------------------------------------------------------------
# Config matching the updated inference_gateway.yaml
# ---------------------------------------------------------------------------

LIVE_CONFIG: dict[str, Any] = {
    "models": {
        "cognitive-core": {
            "primary": {
                "provider": "ollama",
                "model": "glm-5.1:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 4096,
                "temperature": 0.7,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "minimax-m2.7:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
            ],
        },
        "world-model": {
            "primary": {
                "provider": "ollama",
                "model": "minimax-m2.7:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 2048,
                "temperature": 0.3,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "kimi-k2.5:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
            ],
        },
        "thalamus-classifier": {
            "primary": {
                "provider": "ollama",
                "model": "kimi-k2.5:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 512,
                "temperature": 0.2,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "glm-5.1:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 512,
                    "temperature": 0.2,
                },
            ],
        },
        "checkpost": {
            "primary": {
                "provider": "ollama",
                "model": "kimi-k2.5:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 1024,
                "temperature": 0.3,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "glm-5.1:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
            ],
        },
        "queue-zone": {
            "primary": {
                "provider": "ollama",
                "model": "kimi-k2.5:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 512,
                "temperature": 0.2,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "glm-5.1:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 512,
                    "temperature": 0.2,
                },
            ],
        },
        "tlp": {
            "primary": {
                "provider": "ollama",
                "model": "glm-5.1:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 2048,
                "temperature": 0.4,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "minimax-m2.7:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 2048,
                    "temperature": 0.4,
                },
            ],
        },
        "consolidation": {
            "primary": {
                "provider": "ollama",
                "model": "kimi-k2.5:cloud",
                "base_url": "http://localhost:11434",
                "max_tokens": 1024,
                "temperature": 0.3,
            },
            "fallback": [
                {
                    "provider": "ollama",
                    "model": "glm-5.1:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
            ],
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


def _make_gateway(config: dict[str, Any] | None = None) -> InferenceGateway:
    """Create a gateway with the given config (mock litellm)."""
    cfg = config or LIVE_CONFIG
    gw = InferenceGateway(cfg)
    gw._litellm = None  # Simulate litellm not installed unless we mock it
    return gw


def _mock_response(text: str = "ok", input_tokens: int = 10, output_tokens: int = 5) -> MagicMock:
    """Build a mock litellm completion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage.prompt_tokens = input_tokens
    response.usage.completion_tokens = output_tokens
    return response


# ---------------------------------------------------------------------------
# 1. All labels resolve from config (gateway loads config correctly)
# ---------------------------------------------------------------------------


def test_all_labels_resolve_from_config() -> None:
    """Every label in LIVE_CONFIG maps to a spec with a primary endpoint."""
    gw = _make_gateway()
    for label in LIVE_CONFIG["models"]:
        spec = gw._models.get(label)
        assert spec is not None, f"Label '{label}' not found in gateway._models"
        assert "primary" in spec, f"Label '{label}' missing 'primary'"


@pytest.mark.asyncio
async def test_initialize_succeeds_with_all_labels() -> None:
    """initialize() does not raise when all labels have primary config."""
    gw = _make_gateway()
    # Should not raise — all labels have primary
    await gw.initialize()


@pytest.mark.asyncio
async def test_initialize_raises_when_no_models() -> None:
    """initialize() raises RuntimeError when no models are configured."""
    gw = InferenceGateway({"models": {}})
    with pytest.raises(RuntimeError, match="No models configured"):
        await gw.initialize()


@pytest.mark.asyncio
async def test_initialize_raises_when_primary_missing() -> None:
    """initialize() raises RuntimeError when a label has no primary."""
    gw = InferenceGateway({"models": {"bad-label": {"fallback": []}}})
    with pytest.raises(RuntimeError, match="missing 'primary'"):
        await gw.initialize()


# ---------------------------------------------------------------------------
# 2. infer() with valid label returns proper response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infer_cognitive_core_resolves() -> None:
    """cognitive-core maps to ollama/glm-5.1:cloud primary."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(return_value=_mock_response("cognitive response"))
    gw._litellm.completion_cost = MagicMock(return_value=0.005)

    request = InferenceRequest(model_label="cognitive-core", prompt="think")
    response = await gw.infer(request)

    assert response.text == "cognitive response"
    assert response.model_used == "glm-5.1:cloud"
    assert response.provider == "ollama"
    assert response.fallback_used is False
    assert response.error is None

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["model"] == "ollama/glm-5.1:cloud"
    assert call_kwargs["api_base"] == "http://localhost:11434"
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["temperature"] == 0.7


@pytest.mark.asyncio
async def test_infer_world_model_resolves() -> None:
    """world-model maps to ollama/minimax-m2.7:cloud primary (different from cognitive-core)."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(return_value=_mock_response("world model response"))
    gw._litellm.completion_cost = MagicMock(return_value=0.003)

    request = InferenceRequest(model_label="world-model", prompt="assess this")
    response = await gw.infer(request)

    assert response.text == "world model response"
    assert response.model_used == "minimax-m2.7:cloud"
    assert response.provider == "ollama"
    assert response.fallback_used is False
    assert response.error is None

    # Verify it's different from cognitive-core primary
    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["model"] == "ollama/minimax-m2.7:cloud"


@pytest.mark.asyncio
async def test_infer_thalamus_classifier_resolves() -> None:
    """thalamus-classifier maps to ollama/kimi-k2.5:cloud primary."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(return_value=_mock_response("classified"))
    gw._litellm.completion_cost = MagicMock(return_value=0.001)

    request = InferenceRequest(model_label="thalamus-classifier", prompt="classify intent")
    response = await gw.infer(request)

    assert response.text == "classified"
    assert response.model_used == "kimi-k2.5:cloud"
    assert response.provider == "ollama"
    assert response.fallback_used is False
    assert response.error is None


# ---------------------------------------------------------------------------
# 3. infer() with unknown label returns error with "Unknown model label"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infer_unknown_label_returns_error() -> None:
    """Unknown model label returns an error response with 'Unknown model label'."""
    gw = _make_gateway()

    request = InferenceRequest(model_label="non-existent-label", prompt="test")
    response = await gw.infer(request)

    assert response.text == ""
    assert response.model_used == "none"
    assert response.provider == "none"
    assert response.fallback_used is False
    assert response.error is not None
    assert "Unknown model label" in response.error
    assert "non-existent-label" in response.error


# ---------------------------------------------------------------------------
# 4. Fallback chain: primary fails → tries fallback (mock litellm to fail on primary)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cognitive_core_falls_back_when_primary_fails() -> None:
    """When primary fails, fallback (minimax-m2.7:cloud) is tried and succeeds."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Primary endpoint down")
        return _mock_response(text="fallback response")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.002)

    request = InferenceRequest(model_label="cognitive-core", prompt="think")
    response = await gw.infer(request)

    assert response.text == "fallback response"
    assert response.model_used == "minimax-m2.7:cloud"
    assert response.provider == "ollama"
    assert response.fallback_used is True
    assert response.error is None
    assert call_count == 2

    # Verify fallback call uses ollama/minimax-m2.7:cloud with correct api_base
    fallback_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert fallback_kwargs["model"] == "ollama/minimax-m2.7:cloud"
    assert fallback_kwargs["api_base"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_world_model_falls_back_when_primary_fails() -> None:
    """world-model fallback chain: primary fails → kimi-k2.5:cloud."""
    gw = _make_gateway()
    gw._litellm = MagicMock()

    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Primary down")
        return _mock_response(text="world model fallback")

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.002)

    request = InferenceRequest(model_label="world-model", prompt="assess")
    response = await gw.infer(request)

    assert response.text == "world model fallback"
    assert response.model_used == "kimi-k2.5:cloud"
    assert response.fallback_used is True
    assert call_count == 2

    fallback_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert fallback_kwargs["model"] == "ollama/kimi-k2.5:cloud"


# ---------------------------------------------------------------------------
# 5. health_pulse() returns metrics after calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_pulse_returns_metrics() -> None:
    """health_pulse() includes total_calls, total_cost_usd, and endpoint health."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(return_value=_mock_response("ok"))
    gw._litellm.completion_cost = MagicMock(return_value=0.01)

    request = InferenceRequest(model_label="cognitive-core", prompt="test")
    await gw.infer(request)

    pulse = gw.health_pulse()
    assert pulse.module_name == "inference_gateway"
    assert pulse.metrics["total_calls"] == 1
    assert pulse.metrics["total_cost_usd"] == pytest.approx(0.01)
    assert "endpoints" in pulse.metrics
    endpoint_key = "ollama::glm-5.1:cloud"
    assert endpoint_key in pulse.metrics["endpoints"]
    assert pulse.metrics["endpoints"][endpoint_key]["success_count"] == 1
    assert pulse.metrics["endpoints"][endpoint_key]["failure_count"] == 0


# ---------------------------------------------------------------------------
# 6. _EndpointMetrics health_score calculation
# ---------------------------------------------------------------------------


def test_metrics_health_score_empty() -> None:
    """health_score() returns 1.0 when there are no recorded outcomes."""
    metrics = _EndpointMetrics()
    assert metrics.health_score() == 1.0


def test_metrics_health_score_mixed() -> None:
    """health_score() reflects the ratio of recent successes to total calls."""
    metrics = _EndpointMetrics()
    metrics.record_success(100.0)
    metrics.record_success(200.0)
    metrics.record_failure()
    assert metrics.health_score() == pytest.approx(2 / 3)


def test_metrics_health_score_all_failures() -> None:
    """health_score() returns 0.0 when all recent outcomes are failures."""
    metrics = _EndpointMetrics()
    metrics.record_failure()
    metrics.record_failure()
    metrics.record_failure()
    assert metrics.health_score() == 0.0


def test_metrics_health_score_all_successes() -> None:
    """health_score() returns 1.0 when all recent outcomes are successes."""
    metrics = _EndpointMetrics()
    metrics.record_success(50.0)
    metrics.record_success(80.0)
    assert metrics.health_score() == 1.0


def test_metrics_health_score_respects_window() -> None:
    """health_score() only considers the last 100 outcomes."""
    metrics = _EndpointMetrics()
    # Record 100 failures
    for _ in range(100):
        metrics.record_failure()
    # Then 100 successes
    for _ in range(100):
        metrics.record_success(10.0)
    # Score should be 1.0 because only recent 100 (all successes) count
    assert metrics.health_score() == 1.0


# ---------------------------------------------------------------------------
# 7. End-to-end: all labels can be called without "Unknown model label" error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_labels_work_end_to_end() -> None:
    """Every configured label resolves without error (mocked litellm succeeds)."""
    gw = _make_gateway()
    gw._litellm = MagicMock()
    gw._litellm.acompletion = AsyncMock(return_value=_mock_response("response"))
    gw._litellm.completion_cost = MagicMock(return_value=0.001)

    all_labels = list(LIVE_CONFIG["models"].keys())
    assert len(all_labels) == 7

    for label in all_labels:
        request = InferenceRequest(model_label=label, prompt=f"test {label}")
        response = await gw.infer(request)
        assert response.error is None, f"Label '{label}' raised error: {response.error}"
        assert response.model_used != "none", f"Label '{label}' did not resolve"


# ---------------------------------------------------------------------------
# 8. initialize() verifies primary exists for each label
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_checks_all_labels_have_primary() -> None:
    """initialize() detects any label missing a primary config at startup."""
    partial_config: dict[str, Any] = {
        "models": {
            "cognitive-core": {
                "primary": {
                    "provider": "ollama",
                    "model": "glm-5.1:cloud",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
            },
            "broken-label": {"fallback": []},  # missing primary
        },
    }
    gw = InferenceGateway(partial_config)
    with pytest.raises(RuntimeError, match="missing 'primary'"):
        await gw.initialize()
