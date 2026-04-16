"""Innate Response — Layer 2 automatic recovery.

Per DD-015, Layer 2 uses NO LLM. Pure rule-based responses:
  - Module restart (with exponential backoff)
  - Circuit breakers for repeated failures
  - Performance degradation handling
  - Resource exhaustion triage
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class _CircuitBreaker:
    """Simple circuit breaker per module."""

    CLOSED = "closed"         # Normal operation
    OPEN = "open"             # Bypassing module due to repeated failures
    HALF_OPEN = "half_open"   # Testing if recovery happened

    def __init__(
        self,
        error_threshold: int = 3,
        window_minutes: int = 10,
        cooldown_seconds: int = 60,
    ) -> None:
        self.error_threshold = error_threshold
        self.window_seconds = window_minutes * 60
        self.cooldown_seconds = cooldown_seconds
        self.state = self.CLOSED
        self._recent_errors: deque[float] = deque()
        self._opened_at: float | None = None

    def record_error(self) -> None:
        now = time.time()
        self._recent_errors.append(now)
        # Purge old errors outside the window
        cutoff = now - self.window_seconds
        while self._recent_errors and self._recent_errors[0] < cutoff:
            self._recent_errors.popleft()
        if len(self._recent_errors) >= self.error_threshold:
            self.state = self.OPEN
            self._opened_at = now

    def record_success(self) -> None:
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self._recent_errors.clear()
            self._opened_at = None

    def check(self) -> str:
        """Returns current state, transitioning to HALF_OPEN after cooldown."""
        if (
            self.state == self.OPEN
            and self._opened_at
            and time.time() - self._opened_at > self.cooldown_seconds
        ):
            self.state = self.HALF_OPEN
        return self.state


class InnateResponse(ModuleInterface):
    """Rule-based automatic response to anomalies."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle_manager: Any,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("innate_response", config)
        self.event_bus = event_bus or get_event_bus()
        self.lifecycle = lifecycle_manager

        response_cfg = config.get("innate_response", {})
        self.restart_attempts = response_cfg.get("restart_attempts", 3)
        self.restart_backoff = response_cfg.get("restart_backoff_seconds", [0, 30, 120])

        cb_cfg = response_cfg.get("circuit_breaker", {})
        self.cb_error_threshold = cb_cfg.get("error_count_threshold", 3)
        self.cb_window_minutes = cb_cfg.get("error_window_minutes", 10)
        self.cb_cooldown_seconds = cb_cfg.get("cooldown_seconds", 60)

        self._circuit_breakers: dict[str, _CircuitBreaker] = defaultdict(
            lambda: _CircuitBreaker(
                self.cb_error_threshold,
                self.cb_window_minutes,
                self.cb_cooldown_seconds,
            )
        )
        self._restart_history: dict[str, list[float]] = defaultdict(list)
        self._response_count = 0
        self._escalated_count = 0

    async def initialize(self) -> None:
        await self.event_bus.subscribe("health.anomaly", self._handle_anomaly)

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        pass

    async def _handle_anomaly(self, payload: dict[str, Any]) -> None:
        """Respond to a health anomaly."""
        module_name = payload.get("module_name")
        status = payload.get("status")
        if not module_name:
            return

        self._response_count += 1
        cb = self._circuit_breakers[module_name]

        logger.info(
            "Innate response: module=%s status=%s circuit=%s",
            module_name, status, cb.check(),
        )

        try:
            if status == "unresponsive":
                await self._handle_unresponsive(module_name, cb)
            elif status == "critical":
                await self._handle_critical(module_name, cb)
            elif status == "error":
                await self._handle_error(module_name, cb)
            elif status == "degraded":
                await self._handle_degraded(module_name)
        except Exception as exc:
            logger.exception("Innate response error: %s", exc)

    async def _handle_unresponsive(
        self,
        module_name: str,
        cb: _CircuitBreaker,
    ) -> None:
        """Module stopped pulsing — attempt restart."""
        if cb.check() == _CircuitBreaker.OPEN:
            await self._escalate(
                module_name,
                "ERROR",
                "Module unresponsive; circuit breaker OPEN. Needs human intervention.",
            )
            return

        restarted = await self._try_restart(module_name)
        if restarted:
            cb.record_success()
        else:
            cb.record_error()
            if cb.check() == _CircuitBreaker.OPEN:
                await self._escalate(
                    module_name,
                    "CRITICAL",
                    "Module failed to restart after multiple attempts. "
                    "Circuit breaker opened.",
                )

    async def _handle_critical(
        self,
        module_name: str,
        cb: _CircuitBreaker,
    ) -> None:
        """Critical error — restart and escalate in parallel."""
        cb.record_error()
        await self._try_restart(module_name)
        await self._escalate(
            module_name,
            "CRITICAL",
            "Module reported CRITICAL status. Restart attempted.",
        )

    async def _handle_error(
        self,
        module_name: str,
        cb: _CircuitBreaker,
    ) -> None:
        """Recoverable error — note it, may trigger restart on repeat."""
        cb.record_error()
        if cb.check() == _CircuitBreaker.OPEN:
            await self._try_restart(module_name)

    async def _handle_degraded(self, module_name: str) -> None:
        """Degraded performance — publish load-shed signal.

        Modules listening for load-shed events can reduce their work
        (e.g., pause daydreaming, reduce retrieval depth, etc.).
        """
        await self.event_bus.publish(
            "health.load_shed",
            {"module_name": module_name, "severity": "degraded"},
        )

    async def _try_restart(self, module_name: str) -> bool:
        """Attempt to restart a module with backoff."""
        history = self._restart_history[module_name]
        attempt_idx = len(history)
        if attempt_idx >= self.restart_attempts:
            # Already tried max attempts
            return False

        backoff = self.restart_backoff[
            min(attempt_idx, len(self.restart_backoff) - 1)
        ]
        if backoff > 0:
            await asyncio.sleep(backoff)

        history.append(time.time())
        success = await self.lifecycle.restart_module(module_name)
        if success:
            # Reset history on successful restart
            self._restart_history[module_name] = []
            logger.info("Innate response: successfully restarted %s", module_name)
        return success

    async def _escalate(
        self,
        module_name: str,
        severity: str,
        message: str,
    ) -> None:
        """Escalate to the human (Layer 4)."""
        self._escalated_count += 1
        await self.event_bus.publish(
            "health.escalation",
            {
                "module_name": module_name,
                "severity": severity,
                "message": message,
                "what_tried": [
                    f"Restart attempts: {len(self._restart_history.get(module_name, []))}",
                ],
                "timestamp": time.time(),
            },
        )
        logger.error(
            "Escalation: module=%s severity=%s — %s",
            module_name, severity, message,
        )

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "responses_handled": self._response_count,
                "escalations": self._escalated_count,
                "open_circuits": [
                    name for name, cb in self._circuit_breakers.items()
                    if cb.check() == _CircuitBreaker.OPEN
                ],
            },
        )
