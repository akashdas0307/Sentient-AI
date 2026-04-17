"""Unit tests for src/sentient/sleep/scheduler.py."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.sleep.scheduler import SleepScheduler, SleepStage

# Fixtures are provided by tests/unit/sleep/conftest.py


# ---------------------------------------------------------------------------
# SleepStage enum
# ---------------------------------------------------------------------------

class TestSleepStageEnum:
    def test_all_values_present(self):
        assert SleepStage.AWAKE.value == "awake"
        assert SleepStage.SETTLING.value == "settling"
        assert SleepStage.MAINTENANCE.value == "maintenance"
        assert SleepStage.DEEP_CONSOLIDATION.value == "deep_consolidation"
        assert SleepStage.PRE_WAKE.value == "pre_wake"
        assert len(SleepStage) == 5


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_min_max_hours_parsed(self, mock_event_bus, mock_lifecycle, mock_memory):
        config = {
            "duration": {"min_hours": 7, "max_hours": 10},
            "stages": {"settling_minutes": 45, "pre_wake_minutes": 45},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
        }
        scheduler = SleepScheduler(config, mock_lifecycle, mock_memory, mock_event_bus)
        assert scheduler.min_hours == 7
        assert scheduler.max_hours == 10

    def test_sleep_wake_hours_parsed(self, mock_event_bus, mock_lifecycle, mock_memory):
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 45, "pre_wake_minutes": 45},
            "default_circadian": {"sleep_hour": 23, "wake_hour": 6},
        }
        scheduler = SleepScheduler(config, mock_lifecycle, mock_memory, mock_event_bus)
        assert scheduler.sleep_hour == 23
        assert scheduler.wake_hour == 6

    def test_defaults_when_missing(self, mock_event_bus, mock_lifecycle, mock_memory):
        scheduler = SleepScheduler({}, mock_lifecycle, mock_memory, mock_event_bus)
        assert scheduler.min_hours == 6
        assert scheduler.max_hours == 12
        assert scheduler.sleep_hour == 23
        assert scheduler.wake_hour == 7

    def test_stages_parsed(self, mock_event_bus, mock_lifecycle, mock_memory):
        config = {
            "stages": {"settling_minutes": 30, "pre_wake_minutes": 20},
        }
        scheduler = SleepScheduler(config, mock_lifecycle, mock_memory, mock_event_bus)
        assert scheduler.settling_minutes == 30
        assert scheduler.pre_wake_minutes == 20

    def test_initial_state(self, scheduler):
        assert scheduler.current_stage == SleepStage.AWAKE
        assert scheduler._sleep_cycle_count == 0
        assert scheduler._checkpoint == {}
        assert scheduler._wake_up_inbox == []


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    @pytest.mark.asyncio
    async def test_subscribes_to_health_escalation(self, scheduler, mock_event_bus):
        await scheduler.initialize()
        mock_event_bus.subscribe.assert_any_call(
            "health.escalation", scheduler._handle_emergency
        )

    @pytest.mark.asyncio
    async def test_subscribes_to_input_received(self, scheduler, mock_event_bus):
        await scheduler.initialize()
        mock_event_bus.subscribe.assert_any_call(
            "input.received", scheduler._handle_input_during_sleep
        )


# ---------------------------------------------------------------------------
# start() / shutdown()
# ---------------------------------------------------------------------------

class TestStartShutdown:
    @pytest.mark.asyncio
    async def test_start_creates_scheduler_task(self, scheduler, mock_event_bus):
        await scheduler.start()
        assert scheduler._scheduler_task is not None
        assert isinstance(scheduler._scheduler_task, asyncio.Task)
        scheduler._scheduler_task.cancel()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_scheduler_task(self, scheduler, mock_event_bus):
        await scheduler.start()
        await scheduler.shutdown()
        # Allow event loop to process the cancellation
        await asyncio.sleep(0)
        # Task should be cancelled (will raise CancelledError on await)
        assert scheduler._scheduler_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_current_sleep_task(self, scheduler, mock_event_bus):
        await scheduler.start()
        await scheduler.shutdown()
        # No current sleep task initially, should not raise
        assert scheduler._current_sleep_task is None or scheduler._current_sleep_task.cancelled()


# ---------------------------------------------------------------------------
# _is_sleep_time()
# ---------------------------------------------------------------------------

class TestIsSleepTime:
    def _make(self, config, mock_event_bus, mock_lifecycle, mock_memory):
        return SleepScheduler(config, mock_lifecycle, mock_memory, mock_event_bus)

    def _hour(self, hour: int):
        mock_now = MagicMock()
        mock_now.hour = hour
        return mock_now

    def test_hour_within_window_no_crossing(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=22, wake=7 — window crosses midnight. 23 is within."""
        config = {
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(23)
            assert scheduler._is_sleep_time() is True

    def test_hour_before_sleep_window(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=22, wake=7 — 14 is outside."""
        config = {
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(14)
            assert scheduler._is_sleep_time() is False

    def test_hour_inside_non_crossing_window(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=10, wake=18 — 13 is inside."""
        config = {
            "default_circadian": {"sleep_hour": 10, "wake_hour": 18},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(13)
            assert scheduler._is_sleep_time() is True

    def test_hour_outside_non_crossing_window(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=10, wake=18 — 20 is outside."""
        config = {
            "default_circadian": {"sleep_hour": 10, "wake_hour": 18},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(20)
            assert scheduler._is_sleep_time() is False

    def test_midnight_crossing_window_sleep_23_wake_7(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=23, wake=7 — midnight (0) is inside the window."""
        config = {
            "default_circadian": {"sleep_hour": 23, "wake_hour": 7},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(0)
            assert scheduler._is_sleep_time() is True

    def test_wake_hour_boundary_excluded(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=22, wake=7 — wake hour 7 itself is NOT in sleep window."""
        config = {
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(7)
            assert scheduler._is_sleep_time() is False

    def test_sleep_hour_boundary_included(self, mock_event_bus, mock_lifecycle, mock_memory):
        """sleep=22, wake=7 — sleep hour 22 itself IS in window."""
        config = {
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "duration": {},
            "stages": {},
        }
        scheduler = self._make(config, mock_event_bus, mock_lifecycle, mock_memory)
        with patch("sentient.sleep.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = self._hour(22)
            assert scheduler._is_sleep_time() is True


# ---------------------------------------------------------------------------
# enter_sleep()
# ---------------------------------------------------------------------------

class TestEnterSleep:
    @pytest.mark.asyncio
    async def test_when_awake_increments_cycle_count(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        assert scheduler._sleep_cycle_count == 0
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.enter_sleep(requested_hours=1.0)
        assert scheduler._sleep_cycle_count == 1

    @pytest.mark.asyncio
    async def test_when_awake_creates_sleep_task(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.enter_sleep(requested_hours=0.1)
        assert scheduler._current_sleep_task is not None

    @pytest.mark.asyncio
    async def test_when_not_awake_ignored(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.MAINTENANCE
        initial_count = scheduler._sleep_cycle_count
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.enter_sleep()
        assert scheduler._sleep_cycle_count == initial_count

    @pytest.mark.asyncio
    async def test_requested_hours_clamped_to_max(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        # Request 100 hours — should be clamped to max_hours (12)
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.enter_sleep(requested_hours=100.0)
        # Duration should be 12 * 3600
        assert scheduler._current_sleep_duration_seconds == 12 * 3600

    @pytest.mark.asyncio
    async def test_requested_hours_clamped_to_min(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        # Request 0.1 hours — should be clamped to min_hours (6)
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.enter_sleep(requested_hours=0.1)
        assert scheduler._current_sleep_duration_seconds == 6 * 3600


# ---------------------------------------------------------------------------
# _enter_stage()
# ---------------------------------------------------------------------------

class TestEnterStage:
    @pytest.mark.asyncio
    async def test_transitions_stage(self, scheduler, mock_event_bus):
        await scheduler._enter_stage(SleepStage.MAINTENANCE)
        assert scheduler.current_stage == SleepStage.MAINTENANCE

    @pytest.mark.asyncio
    async def test_publishes_transition_event(self, scheduler, mock_event_bus):
        scheduler._sleep_cycle_count = 5
        await scheduler._enter_stage(SleepStage.SETTLING)
        mock_event_bus.publish.assert_called_once_with(
            "sleep.stage.transition",
            {"stage": "settling", "cycle": 5},
        )


# ---------------------------------------------------------------------------
# _sleep_sequence()
# ---------------------------------------------------------------------------

class TestSleepSequence:
    @pytest.mark.asyncio
    async def test_all_four_stages_run_in_order(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler.current_stage = SleepStage.AWAKE
        scheduler._sleep_cycle_count = 0

        # Mock asyncio.sleep to complete instantly
        async def fake_sleep(*args, **kwargs):
            pass

        calls = []
        original_enter = scheduler._enter_stage

        async def tracked_enter(stage):
            calls.append(stage)
            await original_enter(stage)

        scheduler._enter_stage = tracked_enter

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._sleep_sequence(0.2)  # short duration

        assert calls == [
            SleepStage.SETTLING,
            SleepStage.MAINTENANCE,
            SleepStage.DEEP_CONSOLIDATION,
            SleepStage.PRE_WAKE,
        ]
        assert scheduler.current_stage == SleepStage.AWAKE  # final state after wake_up

    @pytest.mark.asyncio
    async def test_deep_minutes_calculation(self, scheduler, mock_event_bus, mock_lifecycle):
        """Verify deep consolidation minutes are computed correctly."""
        scheduler.current_stage = SleepStage.AWAKE
        scheduler._sleep_cycle_count = 1
        scheduler.settling_minutes = 10
        scheduler.pre_wake_minutes = 10

        # With total=1h, settling=10, pre_wake=10, maintenance=61 (cycle%60=1)
        # deep = 60 - 10 - 61 - 10 = -21 → clamped to 30
        deep_minutes_seen = None

        original_run = scheduler._run_deep_consolidation

        async def capture_deep(minutes):
            nonlocal deep_minutes_seen
            deep_minutes_seen = minutes
            await original_run(minutes)

        scheduler._run_deep_consolidation = capture_deep

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._sleep_sequence(1.0)

        assert deep_minutes_seen == 30  # clamped to minimum


# ---------------------------------------------------------------------------
# _run_maintenance()
# ---------------------------------------------------------------------------

class TestRunMaintenance:
    @pytest.mark.asyncio
    async def test_calls_lifecycle_pause_for_sleep(self, scheduler, mock_lifecycle):
        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_maintenance(5)
        mock_lifecycle.pause_for_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_maintenance_event(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler._sleep_cycle_count = 3
        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_maintenance(5)
        mock_event_bus.publish.assert_called_with(
            "sleep.maintenance.running",
            {"cycle": 3},
        )


# ---------------------------------------------------------------------------
# _run_deep_consolidation()
# ---------------------------------------------------------------------------

class TestRunDeepConsolidation:
    @pytest.mark.asyncio
    async def test_publishes_deep_start_event(self, scheduler, mock_event_bus):
        scheduler._sleep_cycle_count = 2
        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_deep_consolidation(5)
        mock_event_bus.publish.assert_any_call(
            "sleep.deep_consolidation.start",
            {"cycle": 2},
        )


# ---------------------------------------------------------------------------
# _job_memory_consolidation()
# ---------------------------------------------------------------------------

class TestJobMemoryConsolidation:
    @pytest.mark.asyncio
    async def test_with_memory_logs_count(self, scheduler, mock_memory):
        mock_memory.count = AsyncMock(return_value=42)
        await scheduler._job_memory_consolidation()
        mock_memory.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_memory_returns_early(self, scheduler):
        scheduler.memory = None
        # Should not raise
        await scheduler._job_memory_consolidation()


# ---------------------------------------------------------------------------
# _run_pre_wake()
# ---------------------------------------------------------------------------

class TestRunPreWake:
    @pytest.mark.asyncio
    async def test_calls_lifecycle_resume_from_sleep(self, scheduler, mock_lifecycle):
        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_pre_wake()
        mock_lifecycle.resume_from_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_handoff_ready_event(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler._sleep_cycle_count = 3
        scheduler._current_sleep_duration_seconds = 3600.0
        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_pre_wake()

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        assert call_args[0][0] == "sleep.handoff.ready"
        handoff = call_args[0][1]["handoff"]
        assert handoff["cycle"] == 3


# ---------------------------------------------------------------------------
# _wake_up()
# ---------------------------------------------------------------------------

class TestWakeUp:
    @pytest.mark.asyncio
    async def test_transitions_to_awake(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.PRE_WAKE
        scheduler._wake_up_inbox = [{"id": 1}, {"id": 2}]
        await scheduler._wake_up()
        assert scheduler.current_stage == SleepStage.AWAKE

    @pytest.mark.asyncio
    async def test_publishes_wake_event(self, scheduler, mock_event_bus):
        scheduler._sleep_cycle_count = 4
        await scheduler._wake_up()
        mock_event_bus.publish.assert_called_with(
            "sleep.wake",
            {"cycle": 4, "wake_up_inbox_count": 0},
        )

    @pytest.mark.asyncio
    async def test_clears_wake_up_inbox(self, scheduler, mock_event_bus):
        scheduler._wake_up_inbox = [{"id": 1}, {"id": 2}, {"id": 3}]
        await scheduler._wake_up()
        assert scheduler._wake_up_inbox == []


# ---------------------------------------------------------------------------
# _estimate_needed_duration()
# ---------------------------------------------------------------------------

class TestEstimateNeededDuration:
    def test_returns_min_hours(self, scheduler):
        scheduler.min_hours = 7
        scheduler.max_hours = 12
        result = scheduler._estimate_needed_duration()
        assert result == 7

    def test_returns_within_bounds(self, scheduler):
        for _ in range(10):
            result = scheduler._estimate_needed_duration()
            assert scheduler.min_hours <= result <= scheduler.max_hours


# ---------------------------------------------------------------------------
# _handle_emergency()
# ---------------------------------------------------------------------------

class TestHandleEmergency:
    @pytest.mark.asyncio
    async def test_critical_triggers_emergency_wake(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.MAINTENANCE
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_emergency({"severity": "CRITICAL"})
            mock_ew.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_down_triggers_emergency_wake(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.SETTLING
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_emergency({"severity": "SYSTEM_DOWN"})
            mock_ew.assert_called_once()

    @pytest.mark.asyncio
    async def test_when_awake_ignored(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_emergency({"severity": "CRITICAL"})
            mock_ew.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_critical_ignored(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.MAINTENANCE
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_emergency({"severity": "WARNING"})
            mock_ew.assert_not_called()


# ---------------------------------------------------------------------------
# _emergency_wake()
# ---------------------------------------------------------------------------

class TestEmergencyWake:
    @pytest.mark.asyncio
    async def test_cancels_current_sleep_task(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler.current_stage = SleepStage.AWAKE
        scheduler._sleep_cycle_count = 1
        # Start a real sleep sequence that will get cancelled
        with patch("asyncio.sleep"):
            await scheduler.enter_sleep(requested_hours=1.0)
            task = scheduler._current_sleep_task
            assert task is not None

        with patch("asyncio.sleep"):
            await scheduler._emergency_wake()

        # Task should be cancelled (give event loop time to process cancellation)
        await asyncio.sleep(0.05)
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_saves_checkpoint_in_deep_consolidation(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler.current_stage = SleepStage.DEEP_CONSOLIDATION
        scheduler._sleep_cycle_count = 1
        scheduler._current_sleep_task = None  # no task to cancel

        with patch("asyncio.sleep"):
            await scheduler._emergency_wake()

        assert scheduler._checkpoint["stage"] == "deep_consolidation"
        assert "interrupted_at" in scheduler._checkpoint

    @pytest.mark.asyncio
    async def test_no_checkpoint_if_not_deep_consolidation(self, scheduler, mock_event_bus, mock_lifecycle):
        scheduler.current_stage = SleepStage.SETTLING
        scheduler._sleep_cycle_count = 1
        scheduler._current_sleep_task = None

        with patch("asyncio.sleep"):
            await scheduler._emergency_wake()

        assert scheduler._checkpoint == {}


# ---------------------------------------------------------------------------
# _handle_input_during_sleep()
# ---------------------------------------------------------------------------

class TestHandleInputDuringSleep:
    @pytest.mark.asyncio
    async def test_tier1_emergency_wake(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.MAINTENANCE
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_input_during_sleep({"priority": 1})
            mock_ew.assert_called_once()

    @pytest.mark.asyncio
    async def test_tier2_goes_to_inbox(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.MAINTENANCE
        payload = {"priority": 2, "content": "important"}
        await scheduler._handle_input_during_sleep(payload)
        assert payload in scheduler._wake_up_inbox

    @pytest.mark.asyncio
    async def test_tier3_routine_goes_to_inbox(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.DEEP_CONSOLIDATION
        payload = {"priority": 3, "content": "routine"}
        await scheduler._handle_input_during_sleep(payload)
        assert payload in scheduler._wake_up_inbox

    @pytest.mark.asyncio
    async def test_when_awake_ignored(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.AWAKE
        with patch.object(scheduler, "_emergency_wake", new_callable=AsyncMock) as mock_ew:
            await scheduler._handle_input_during_sleep({"priority": 1})
            mock_ew.assert_not_called()


# ---------------------------------------------------------------------------
# health_pulse()
# ---------------------------------------------------------------------------

class TestHealthPulse:
    def test_returns_correct_metrics(self, scheduler):
        scheduler.current_stage = SleepStage.MAINTENANCE
        scheduler._sleep_cycle_count = 5
        scheduler._wake_up_inbox = [{"a": 1}]
        scheduler._checkpoint = {"x": 1}

        pulse = scheduler.health_pulse()
        assert pulse.module_name == "sleep_scheduler"
        assert pulse.metrics["current_stage"] == "maintenance"
        assert pulse.metrics["sleep_cycle_count"] == 5
        assert pulse.metrics["wake_up_inbox_size"] == 1
        assert pulse.metrics["checkpoint_present"] is True

    def test_checkpoint_present_false_when_empty(self, scheduler):
        scheduler._checkpoint = {}
        pulse = scheduler.health_pulse()
        assert pulse.metrics["checkpoint_present"] is False


# ---------------------------------------------------------------------------
# _schedule_loop()
# ---------------------------------------------------------------------------

class TestScheduleLoop:
    @pytest.mark.asyncio
    async def test_skips_sleep_when_not_awake(self, scheduler, mock_event_bus):
        scheduler.current_stage = SleepStage.SETTLING
        with patch("sentient.sleep.scheduler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Cancel on first sleep call so the loop exits cleanly
            mock_sleep.side_effect = asyncio.CancelledError()
            scheduler._scheduler_task = asyncio.create_task(scheduler._schedule_loop())
            try:
                await asyncio.wait_for(scheduler._scheduler_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            # sleep should have been called (check runs every minute)
            assert mock_sleep.call_count >= 1