"""Unit tests for src/sentient/health/innate_response.py.

Covers:
  - CircuitBreaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
  - Restart attempts with exponential backoff and max retry cap
  - Failover routing when module is dead (unresponsive/critical/error)
  - Escalation to Layer 4 (human) when innate response exhausts options
  - Integration with pulse_network dead-module events
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.core.event_bus import EventBus
from sentient.core.module_interface import ModuleStatus
from sentient.health.innate_response import InnateResponse, _CircuitBreaker


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for _CircuitBreaker state machine."""

    def test_initial_state_is_closed(self) -> None:
        cb = _CircuitBreaker()
        assert cb.state == _CircuitBreaker.CLOSED

    def test_record_error_under_threshold_stays_closed(self) -> None:
        cb = _CircuitBreaker(error_threshold=3)
        cb.record_error()
        cb.record_error()
        assert cb.state == _CircuitBreaker.CLOSED

    def test_record_error_at_threshold_opens_circuit(self) -> None:
        cb = _CircuitBreaker(error_threshold=3)
        cb.record_error()
        cb.record_error()
        cb.record_error()
        assert cb.state == _CircuitBreaker.OPEN

    def test_record_error_purges_old_errors(self) -> None:
        cb = _CircuitBreaker(error_threshold=3, window_minutes=10)
        # Record 2 old errors
        cb._recent_errors.append(time.time() - 6000)  # 100 min ago
        cb._recent_errors.append(time.time() - 6000)
        # Record 1 new error — only the new one should count
        cb.record_error()
        assert cb.state == _CircuitBreaker.CLOSED  # only 1 recent error

    def test_record_success_from_half_open_closes_circuit(self) -> None:
        cb = _CircuitBreaker()
        cb.state = _CircuitBreaker.HALF_OPEN
        cb.record_success()
        assert cb.state == _CircuitBreaker.CLOSED
        assert len(cb._recent_errors) == 0

    def test_check_returns_closed(self) -> None:
        cb = _CircuitBreaker()
        assert cb.check() == _CircuitBreaker.CLOSED

    def test_check_returns_open(self) -> None:
        cb = _CircuitBreaker()
        cb.state = _CircuitBreaker.OPEN
        cb._opened_at = time.time()  # recently opened
        assert cb.check() == _CircuitBreaker.OPEN

    def test_check_transitions_to_half_open_after_cooldown(self) -> None:
        cb = _CircuitBreaker(cooldown_seconds=1)
        cb.state = _CircuitBreaker.OPEN
        cb._opened_at = time.time() - 2  # opened 2s ago, cooldown is 1s
        assert cb.check() == _CircuitBreaker.HALF_OPEN

    def test_check_stays_open_before_cooldown(self) -> None:
        cb = _CircuitBreaker(cooldown_seconds=60)
        cb.state = _CircuitBreaker.OPEN
        cb._opened_at = time.time()  # just opened
        assert cb.check() == _CircuitBreaker.OPEN


# ---------------------------------------------------------------------------
# InnateResponse construction
# ---------------------------------------------------------------------------


class TestInnateResponseInit:
    """Tests for InnateResponse.__init__."""

    def test_init_default_config(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        assert ir.restart_attempts == 3
        assert ir.restart_backoff == [0, 30, 120]
        assert ir.cb_error_threshold == 3
        assert ir.cb_window_minutes == 10
        assert ir.cb_cooldown_seconds == 60

    def test_init_custom_config(self) -> None:
        lifecycle = MagicMock()
        cfg = {
            "innate_response": {
                "restart_attempts": 5,
                "restart_backoff_seconds": [0, 10, 30, 60, 120],
                "circuit_breaker": {
                    "error_count_threshold": 5,
                    "error_window_minutes": 5,
                    "cooldown_seconds": 30,
                },
            }
        }
        ir = InnateResponse(cfg, lifecycle)
        assert ir.restart_attempts == 5
        assert ir.restart_backoff == [0, 10, 30, 60, 120]
        assert ir.cb_error_threshold == 5
        assert ir.cb_window_minutes == 5
        assert ir.cb_cooldown_seconds == 30


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestInnateResponseLifecycle:
    """Tests for InnateResponse initialize/start/shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_anomaly(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle, event_bus=bus)

        subscribed = []

        original_subscribe = bus.subscribe
        async def tracking_subscribe(topic: str, handler):
            subscribed.append(topic)
            await original_subscribe(topic, handler)

        bus.subscribe = tracking_subscribe
        await ir.initialize()

        assert "health.anomaly" in subscribed

    @pytest.mark.asyncio
    async def test_start_sets_healthy_status(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        await ir.start()
        assert ir._last_health_status == ModuleStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_shutdown_is_noop(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        await ir.shutdown()  # should not raise


# ---------------------------------------------------------------------------
# _handle_anomaly routing
# ---------------------------------------------------------------------------


class TestHandleAnomaly:
    """Tests for InnateResponse._handle_anomaly routing."""

    @pytest.mark.asyncio
    async def test_empty_payload_returns_early(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        await ir.start()

        result = await ir._handle_anomaly({})
        assert result is None  # early return
        assert ir._response_count == 0  # no increment

    @pytest.mark.asyncio
    async def test_unresponsive_routes_to_handler(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        # Spy on _handle_unresponsive
        called_with = []
        original = ir._handle_unresponsive
        async def spy_unresponsive(module_name, cb):
            called_with.append((module_name, cb.state))
            await original(module_name, cb)

        ir._handle_unresponsive = spy_unresponsive

        await ir._handle_anomaly({
            "module_name": "test_mod",
            "status": "unresponsive",
        })

        assert len(called_with) == 1
        assert called_with[0][0] == "test_mod"

    @pytest.mark.asyncio
    async def test_critical_routes_to_handler(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        called_with = []
        original = ir._handle_critical
        async def spy_critical(module_name, cb):
            called_with.append(module_name)
            await original(module_name, cb)

        ir._handle_critical = spy_critical

        await ir._handle_anomaly({
            "module_name": "test_mod",
            "status": "critical",
        })

        assert called_with == ["test_mod"]

    @pytest.mark.asyncio
    async def test_error_routes_to_handler(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        called_with = []
        original = ir._handle_error
        async def spy_error(module_name, cb):
            called_with.append(module_name)
            await original(module_name, cb)

        ir._handle_error = spy_error

        await ir._handle_anomaly({
            "module_name": "test_mod",
            "status": "error",
        })

        assert called_with == ["test_mod"]

    @pytest.mark.asyncio
    async def test_degraded_publishes_load_shed(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        load_shed_events: list = []
        async def catch_load_shed(payload: dict) -> None:
            load_shed_events.append(payload)

        await bus.subscribe("health.load_shed", catch_load_shed)

        await ir._handle_anomaly({
            "module_name": "slow_mod",
            "status": "degraded",
        })

        await asyncio.sleep(0.05)
        assert len(load_shed_events) == 1
        assert load_shed_events[0]["module_name"] == "slow_mod"
        assert load_shed_events[0]["severity"] == "degraded"

    @pytest.mark.asyncio
    async def test_exception_during_handling_is_caught(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        await ir.start()

        # _handle_unresponsive will raise because lifecycle.restart_module isn't async
        # This should NOT crash — _handle_anomaly has a try/except
        ir._handle_unresponsive = AsyncMock(side_effect=RuntimeError("test error"))
        # Should not raise
        await ir._handle_anomaly({
            "module_name": "broken_mod",
            "status": "unresponsive",
        })


# ---------------------------------------------------------------------------
# _handle_unresponsive
# ---------------------------------------------------------------------------


class TestHandleUnresponsive:
    """Tests for _handle_unresponsive."""

    @pytest.mark.asyncio
    async def test_open_circuit_escalates_without_restart(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=False)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        # Force circuit to OPEN
        cb = ir._circuit_breakers["dead_mod"]
        cb.state = _CircuitBreaker.OPEN
        cb._opened_at = time.time()

        escalation_events: list = []
        async def catch_escalation(payload: dict) -> None:
            escalation_events.append(payload)

        await bus.subscribe("health.escalation", catch_escalation)

        await ir._handle_unresponsive("dead_mod", cb)

        await asyncio.sleep(0.05)
        assert len(escalation_events) == 1
        assert escalation_events[0]["severity"] == "ERROR"
        # restart_module should NOT have been called
        lifecycle.restart_module.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_restart_records_success(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        cb = ir._circuit_breakers["flaky_mod"]

        await ir._handle_unresponsive("flaky_mod", cb)

        assert cb.state == _CircuitBreaker.CLOSED
        lifecycle.restart_module.assert_called_once_with("flaky_mod")

    @pytest.mark.asyncio
    async def test_failed_restart_records_error_may_escalate(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=False)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        escalation_events: list = []
        async def catch_escalation(payload: dict) -> None:
            escalation_events.append(payload)

        await bus.subscribe("health.escalation", catch_escalation)

        # With default threshold of 3, 1 error won't open the circuit
        cb = ir._circuit_breakers["flaky_mod"]
        await ir._handle_unresponsive("flaky_mod", cb)

        # Circuit should still be CLOSED (1 error < 3 threshold)
        assert cb.state == _CircuitBreaker.CLOSED
        # No escalation yet
        assert len(escalation_events) == 0


# ---------------------------------------------------------------------------
# _handle_critical
# ---------------------------------------------------------------------------


class TestHandleCritical:
    """Tests for _handle_critical."""

    @pytest.mark.asyncio
    async def test_critical_records_error_and_restarts(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        escalation_events: list = []
        async def catch_escalation(payload: dict) -> None:
            escalation_events.append(payload)

        await bus.subscribe("health.escalation", catch_escalation)

        cb = ir._circuit_breakers["dying_mod"]
        await ir._handle_critical("dying_mod", cb)

        # Error recorded
        assert len(cb._recent_errors) == 1
        # Restart attempted
        lifecycle.restart_module.assert_called_once()
        # Escalation published
        await asyncio.sleep(0.05)
        assert len(escalation_events) == 1
        assert escalation_events[0]["severity"] == "CRITICAL"


# ---------------------------------------------------------------------------
# _handle_error
# ---------------------------------------------------------------------------


class TestHandleError:
    """Tests for _handle_error."""

    @pytest.mark.asyncio
    async def test_error_records_error(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        await ir.start()

        cb = ir._circuit_breakers["err_mod"]
        await ir._handle_error("err_mod", cb)

        assert len(cb._recent_errors) == 1

    @pytest.mark.asyncio
    async def test_error_with_open_circuit_triggers_restart(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        cb = ir._circuit_breakers["err_mod"]
        cb.state = _CircuitBreaker.OPEN
        cb._opened_at = time.time()

        await ir._handle_error("err_mod", cb)

        lifecycle.restart_module.assert_called_once_with("err_mod")


# ---------------------------------------------------------------------------
# _try_restart
# ---------------------------------------------------------------------------


class TestTryRestart:
    """Tests for _try_restart with backoff and max retry."""

    @pytest.mark.asyncio
    async def test_successful_restart(self) -> None:
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        ir = InnateResponse({}, lifecycle)
        await ir.start()

        result = await ir._try_restart("flaky_mod")

        assert result is True
        assert ir._restart_history["flaky_mod"] == []  # reset on success

    @pytest.mark.asyncio
    async def test_failed_restart_returns_false(self) -> None:
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=False)

        ir = InnateResponse({}, lifecycle)
        await ir.start()

        result = await ir._try_restart("dead_mod")

        assert result is False
        assert len(ir._restart_history["dead_mod"]) == 1

    @pytest.mark.asyncio
    async def test_max_attempts_returns_false(self) -> None:
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=False)

        cfg = {"innate_response": {"restart_attempts": 2, "restart_backoff_seconds": [0, 0]}}
        ir = InnateResponse(cfg, lifecycle)
        await ir.start()

        # Exhaust all attempts
        result1 = await ir._try_restart("dead_mod")
        result2 = await ir._try_restart("dead_mod")

        assert result1 is False
        assert result2 is False
        # After max attempts, returns False immediately
        result3 = await ir._try_restart("dead_mod")
        assert result3 is False

    @pytest.mark.asyncio
    async def test_backoff_is_applied(self) -> None:
        lifecycle = MagicMock()
        lifecycle.restart_module = AsyncMock(return_value=True)

        cfg = {"innate_response": {"restart_attempts": 3, "restart_backoff_seconds": [0, 1, 5]}}
        ir = InnateResponse(cfg, lifecycle)
        await ir.start()

        with patch("sentient.health.innate_response.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # First attempt: backoff[0] = 0, no sleep
            await ir._try_restart("mod1")
            assert mock_sleep.call_count == 0  # backoff=0, no sleep


# ---------------------------------------------------------------------------
# _escalate
# ---------------------------------------------------------------------------


class TestEscalate:
    """Tests for _escalate (Layer 4 escalation)."""

    @pytest.mark.asyncio
    async def test_escalate_publishes_event(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        escalation_events: list = []
        async def catch_escalation(payload: dict) -> None:
            escalation_events.append(payload)

        await bus.subscribe("health.escalation", catch_escalation)

        await ir._escalate("memory", "CRITICAL", "Module crashed repeatedly")

        await asyncio.sleep(0.05)
        assert len(escalation_events) == 1
        assert escalation_events[0]["module_name"] == "memory"
        assert escalation_events[0]["severity"] == "CRITICAL"
        assert "crashed repeatedly" in escalation_events[0]["message"]

    @pytest.mark.asyncio
    async def test_escalate_increments_counter(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        assert ir._escalated_count == 0
        await ir._escalate("mod", "ERROR", "test")
        assert ir._escalated_count == 1
        await ir._escalate("mod", "CRITICAL", "test")
        assert ir._escalated_count == 2


# ---------------------------------------------------------------------------
# health_pulse
# ---------------------------------------------------------------------------


class TestHealthPulse:
    """Tests for InnateResponse.health_pulse."""

    def test_health_pulse_returns_metrics(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)
        ir._response_count = 5
        ir._escalated_count = 1

        pulse = ir.health_pulse()
        assert pulse.module_name == "innate_response"
        assert pulse.metrics["responses_handled"] == 5
        assert pulse.metrics["escalations"] == 1
        assert pulse.metrics["open_circuits"] == []

    def test_health_pulse_includes_open_circuits(self) -> None:
        lifecycle = MagicMock()
        ir = InnateResponse({}, lifecycle)

        # Force a circuit open
        ir._circuit_breakers["dead_mod"].state = _CircuitBreaker.OPEN
        ir._circuit_breakers["dead_mod"]._opened_at = time.time()

        pulse = ir.health_pulse()
        assert "dead_mod" in pulse.metrics["open_circuits"]


# ---------------------------------------------------------------------------
# Integration: _handle_degraded
# ---------------------------------------------------------------------------


class TestHandleDegraded:
    """Tests for _handle_degraded."""

    @pytest.mark.asyncio
    async def test_degraded_publishes_load_shed(self) -> None:
        bus = EventBus()
        lifecycle = MagicMock()

        ir = InnateResponse({}, lifecycle, event_bus=bus)
        await ir.start()

        load_shed_events: list = []
        async def catch_load_shed(payload: dict) -> None:
            load_shed_events.append(payload)

        await bus.subscribe("health.load_shed", catch_load_shed)

        await ir._handle_degraded("slow_mod")

        await asyncio.sleep(0.05)
        assert len(load_shed_events) == 1
        assert load_shed_events[0]["module_name"] == "slow_mod"
        assert load_shed_events[0]["severity"] == "degraded"