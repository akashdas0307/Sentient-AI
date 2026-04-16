"""Inference Gateway — adaptive LLM routing with fallback chain.

Per DD-018, every module that needs LLM inference goes through this gateway.
The gateway handles:
  - Model selection per module (different models for Cognitive Core vs World Model)
  - Cloud preferred → local fallback → heuristic minimum
  - Performance tracking for adaptive routing
  - Cost tracking
  - Prompt caching where supported

Reference: ARCHITECTURE.md §3.8, DESIGN_DECISIONS.md DD-002, DD-018
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class InferenceRequest:
    """A request for LLM inference."""

    model_label: str          # Which configured model (e.g., "cognitive-core")
    prompt: str               # User/main message
    system_prompt: str = ""   # System message
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResponse:
    """Result of an LLM inference call."""

    text: str
    model_used: str           # Which actual model handled the call
    provider: str             # Which provider (anthropic, ollama, etc.)
    fallback_used: bool       # True if primary failed
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


@dataclass
class _EndpointMetrics:
    """Performance tracking for a specific endpoint."""

    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    recent_outcomes: deque = field(default_factory=lambda: deque(maxlen=100))

    def record_success(self, latency_ms: float) -> None:
        self.success_count += 1
        self.total_latency_ms += latency_ms
        self.recent_outcomes.append(("success", latency_ms))

    def record_failure(self) -> None:
        self.failure_count += 1
        self.recent_outcomes.append(("failure", 0))

    def health_score(self) -> float:
        """Recent success rate (0.0-1.0)."""
        if not self.recent_outcomes:
            return 1.0
        successes = sum(1 for outcome, _ in self.recent_outcomes if outcome == "success")
        return successes / len(self.recent_outcomes)


class InferenceGateway(ModuleInterface):
    """Routes LLM inference requests through configured providers.

    Configuration loaded from config/inference_gateway.yaml.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__("inference_gateway", config)
        self._models: dict[str, dict[str, Any]] = config.get("models", {})
        self._routing: dict[str, Any] = config.get("routing", {})
        self._cost_tracking: dict[str, Any] = config.get("cost_tracking", {})
        self._metrics: dict[str, _EndpointMetrics] = {}
        self._total_cost_usd = 0.0
        self._call_count = 0
        self._litellm = None

    async def initialize(self) -> None:
        """Verify provider availability and load litellm."""
        try:
            import litellm
            self._litellm = litellm
            # Disable litellm's verbose logging by default
            litellm.suppress_debug_info = True
            logger.info("Inference Gateway: litellm loaded")
        except ImportError:
            logger.warning(
                "Inference Gateway: litellm not installed — gateway will only "
                "return heuristic fallbacks. Install with: pip install litellm"
            )

        # Verify configured models
        if not self._models:
            raise RuntimeError("No models configured in inference_gateway.yaml")

        for label, spec in self._models.items():
            if "primary" not in spec:
                raise RuntimeError(f"Model '{label}' missing 'primary' config")

    async def start(self) -> None:
        """Begin operation. Connectivity will be tested on first real call."""
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        """Log final cost summary."""
        logger.info(
            "Inference Gateway shutdown — total calls: %d, total cost: $%.4f",
            self._call_count, self._total_cost_usd,
        )

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Run inference with automatic fallback.

        Returns an InferenceResponse with the result, or an error response
        if all endpoints in the fallback chain failed.
        """
        self._call_count += 1
        spec = self._models.get(request.model_label)
        if not spec:
            return InferenceResponse(
                text="",
                model_used="none",
                provider="none",
                fallback_used=False,
                latency_ms=0,
                error=f"Unknown model label: {request.model_label}",
            )

        # Build endpoint chain: primary + fallbacks
        endpoints = [spec["primary"]] + spec.get("fallback", [])

        last_error: str | None = None
        for idx, endpoint in enumerate(endpoints):
            is_fallback = idx > 0
            response = await self._try_endpoint(request, endpoint, is_fallback)
            if response.error is None:
                return response
            last_error = response.error
            logger.info(
                "Endpoint %s/%s failed (%s) — trying next in chain",
                endpoint.get("provider"), endpoint.get("model"), response.error,
            )

        # All endpoints failed
        return InferenceResponse(
            text="",
            model_used="all_failed",
            provider="none",
            fallback_used=True,
            latency_ms=0,
            error=f"All endpoints failed; last error: {last_error}",
        )

    async def _try_endpoint(
        self,
        request: InferenceRequest,
        endpoint: dict[str, Any],
        is_fallback: bool,
    ) -> InferenceResponse:
        """Attempt inference on a specific endpoint."""
        endpoint_key = f"{endpoint.get('provider')}::{endpoint.get('model')}"
        metrics = self._metrics.setdefault(endpoint_key, _EndpointMetrics())

        provider = endpoint.get("provider", "unknown")
        model = endpoint.get("model", "unknown")
        max_tokens = request.max_tokens or endpoint.get("max_tokens", 1024)
        temperature = (
            request.temperature
            if request.temperature is not None
            else endpoint.get("temperature", 0.7)
        )

        if self._litellm is None:
            # Litellm not available — return heuristic minimum
            metrics.record_failure()
            return InferenceResponse(
                text="",
                model_used=model,
                provider=provider,
                fallback_used=is_fallback,
                latency_ms=0,
                error="litellm not installed",
            )

        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        # Construct litellm-format model string
        if provider == "ollama":
            model_str = f"ollama/{model}"
            extra_kwargs = {"api_base": endpoint.get("base_url", "http://localhost:11434")}
        elif provider == "anthropic":
            model_str = f"anthropic/{model}"
            extra_kwargs = {}
        elif provider == "openai":
            model_str = model
            extra_kwargs = {}
        else:
            model_str = f"{provider}/{model}"
            extra_kwargs = {}

        start = time.time()
        try:
            response = await asyncio.wait_for(
                self._litellm.acompletion(
                    model=model_str,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **extra_kwargs,
                ),
                timeout=request.timeout_seconds,
            )
            latency_ms = (time.time() - start) * 1000

            # Extract response
            text = response.choices[0].message.content or ""
            input_tokens = getattr(response.usage, "prompt_tokens", 0)
            output_tokens = getattr(response.usage, "completion_tokens", 0)

            # Estimate cost (litellm provides this for known models)
            cost = 0.0
            try:
                cost = self._litellm.completion_cost(completion_response=response) or 0.0
            except Exception:
                pass
            self._total_cost_usd += cost

            metrics.record_success(latency_ms)
            return InferenceResponse(
                text=text,
                model_used=model,
                provider=provider,
                fallback_used=is_fallback,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        except asyncio.TimeoutError:
            metrics.record_failure()
            return InferenceResponse(
                text="",
                model_used=model,
                provider=provider,
                fallback_used=is_fallback,
                latency_ms=(time.time() - start) * 1000,
                error="timeout",
            )
        except Exception as exc:
            metrics.record_failure()
            return InferenceResponse(
                text="",
                model_used=model,
                provider=provider,
                fallback_used=is_fallback,
                latency_ms=(time.time() - start) * 1000,
                error=str(exc),
            )

    def health_pulse(self) -> HealthPulse:
        endpoint_health = {
            ep: {
                "health_score": m.health_score(),
                "success_count": m.success_count,
                "failure_count": m.failure_count,
            }
            for ep, m in self._metrics.items()
        }
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "total_calls": self._call_count,
                "total_cost_usd": round(self._total_cost_usd, 4),
                "endpoints": endpoint_health,
            },
        )
