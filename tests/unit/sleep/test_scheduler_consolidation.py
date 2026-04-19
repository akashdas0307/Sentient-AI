"""Unit tests for SleepScheduler consolidation integration.

Tests that the scheduler properly wires in the ConsolidationEngine:
- Calls consolidation_engine.consolidate_cycle() when entering deep consolidation
- Does NOT crash if consolidation_engine raises an exception
- Skips consolidation when consolidation_enabled is False
- Falls back to _job_memory_consolidation when no consolidation_engine is provided
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.sleep.scheduler import SleepScheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_consolidation_engine():
    """Mock ConsolidationEngine with async consolidate_cycle."""
    engine = MagicMock()
    engine.consolidate_cycle = AsyncMock(return_value={
        "status": "completed",
        "facts_extracted": 3,
        "patterns_extracted": 2,
        "episodes_processed": 10,
    })
    return engine


@pytest.fixture
def mock_event_bus():
    """Mock EventBus with async publish/subscribe."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()
    yield bus
    bus.reset_mock()
    del bus


@pytest.fixture
def mock_lifecycle():
    """Mock lifecycle manager with async methods."""
    lc = MagicMock()
    lc.pause_for_sleep = AsyncMock()
    lc.resume_from_sleep = AsyncMock()
    lc.request_shutdown = AsyncMock()
    yield lc
    lc.reset_mock()
    del lc


@pytest.fixture
def mock_memory():
    """Mock memory with async count."""
    mem = MagicMock()
    mem.count = AsyncMock(return_value=0)
    yield mem
    mem.reset_mock()
    del mem


@pytest.fixture
def base_config():
    """Base config dict for SleepScheduler with consolidation enabled."""
    return {
        "duration": {"min_hours": 6, "max_hours": 12},
        "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
        "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
        "consolidation_enabled": True,
    }


# ---------------------------------------------------------------------------
# Tests: scheduler with consolidation_engine
# ---------------------------------------------------------------------------

class TestConsolidationEngineIntegration:
    """Tests for scheduler -> consolidation engine integration."""

    @pytest.mark.asyncio
    async def test_calls_consolidation_engine_when_entering_deep_consolidation(
        self, mock_consolidation_engine, mock_event_bus, mock_lifecycle, mock_memory, base_config
    ):
        """When consolidation_engine is present, scheduler calls consolidate_cycle()."""
        scheduler = SleepScheduler(
            base_config, mock_lifecycle, mock_memory,
            consolidation_engine=mock_consolidation_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_deep_consolidation(5)

        mock_consolidation_engine.consolidate_cycle.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_consolidation_result_on_success(
        self, mock_consolidation_engine, mock_event_bus, mock_lifecycle, mock_memory, base_config
    ):
        """On successful consolidation, scheduler logs status, facts, and patterns."""
        scheduler = SleepScheduler(
            base_config, mock_lifecycle, mock_memory,
            consolidation_engine=mock_consolidation_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            with patch("sentient.sleep.scheduler.logger") as mock_logger:
                await scheduler._run_deep_consolidation(5)

        mock_logger.info.assert_any_call(
            "Consolidation completed: %s (facts=%s, patterns=%s)",
            "completed", 3, 2,
        )

    @pytest.mark.asyncio
    async def test_does_not_crash_if_consolidation_engine_raises_exception(
        self, mock_event_bus, mock_lifecycle, mock_memory, base_config
    ):
        """Consolidation failure must NOT crash the sleep cycle."""
        broken_engine = MagicMock()
        broken_engine.consolidate_cycle = AsyncMock(
            side_effect=RuntimeError("Consolidation exploded")
        )
        scheduler = SleepScheduler(
            base_config, mock_lifecycle, mock_memory,
            consolidation_engine=broken_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            # Should not raise — wrapped in try/except
            await scheduler._run_deep_consolidation(5)

    @pytest.mark.asyncio
    async def test_logs_exception_when_consolidation_fails(
        self, mock_event_bus, mock_lifecycle, mock_memory, base_config
    ):
        """Consolidation exceptions are logged, not swallowed silently."""
        broken_engine = MagicMock()
        broken_engine.consolidate_cycle = AsyncMock(
            side_effect=RuntimeError("Consolidation exploded")
        )
        scheduler = SleepScheduler(
            base_config, mock_lifecycle, mock_memory,
            consolidation_engine=broken_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            with patch("sentient.sleep.scheduler.logger") as mock_logger:
                await scheduler._run_deep_consolidation(5)

        # Should have logged an exception
        mock_logger.exception.assert_called()


# ---------------------------------------------------------------------------
# Tests: consolidation_enabled flag
# ---------------------------------------------------------------------------

class TestConsolidationEnabledFlag:
    """Tests for consolidation_enabled config flag."""

    @pytest.mark.asyncio
    async def test_skips_consolidation_when_flag_is_false(
        self, mock_consolidation_engine, mock_event_bus, mock_lifecycle, mock_memory
    ):
        """When consolidation_enabled is False, engine is NOT called."""
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "consolidation_enabled": False,
        }
        scheduler = SleepScheduler(
            config, mock_lifecycle, mock_memory,
            consolidation_engine=mock_consolidation_engine,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            await scheduler._run_deep_consolidation(5)

        mock_consolidation_engine.consolidate_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_defaults_to_true_when_missing(
        self, mock_consolidation_engine, mock_event_bus, mock_lifecycle, mock_memory
    ):
        """When consolidation_enabled is absent from config, defaults to True."""
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            # consolidation_enabled not specified — should default to True
        }
        scheduler = SleepScheduler(
            config, mock_lifecycle, mock_memory,
            consolidation_engine=mock_consolidation_engine,
            event_bus=mock_event_bus,
        )
        assert scheduler.consolidation_enabled is True


# ---------------------------------------------------------------------------
# Tests: fallback to _job_memory_consolidation
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    """Tests for backward-compatible fallback when no consolidation_engine."""

    @pytest.mark.asyncio
    async def test_falls_back_to_job_memory_consolidation_when_no_engine(
        self, mock_event_bus, mock_lifecycle, mock_memory
    ):
        """When consolidation_engine is None, uses _job_memory_consolidation stub."""
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "consolidation_enabled": True,
        }
        scheduler = SleepScheduler(
            config, mock_lifecycle, mock_memory,
            consolidation_engine=None,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            with patch.object(scheduler, "_job_memory_consolidation", new_callable=AsyncMock) as mock_job:
                await scheduler._run_deep_consolidation(5)
                mock_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_when_engine_is_none_and_flag_is_true(
        self, mock_event_bus, mock_lifecycle, mock_memory
    ):
        """Explicit consolidation_enabled=True with no engine still uses fallback."""
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "consolidation_enabled": True,
        }
        scheduler = SleepScheduler(
            config, mock_lifecycle, mock_memory,
            consolidation_engine=None,
            event_bus=mock_event_bus,
        )
        scheduler._sleep_cycle_count = 1

        async def fake_sleep(*args, **kwargs):
            pass

        with patch("asyncio.sleep", new=fake_sleep):
            with patch.object(scheduler, "_job_memory_consolidation", new_callable=AsyncMock) as mock_job:
                await scheduler._run_deep_consolidation(5)
                mock_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_memory_consolidation_still_logs_memory_count(
        self, mock_event_bus, mock_lifecycle, mock_memory
    ):
        """Fallback _job_memory_consolidation still logs the memory count."""
        config = {
            "duration": {"min_hours": 6, "max_hours": 12},
            "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
            "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
            "consolidation_enabled": False,
        }
        scheduler = SleepScheduler(
            config, mock_lifecycle, mock_memory,
            consolidation_engine=None,
            event_bus=mock_event_bus,
        )
        mock_memory.count = AsyncMock(return_value=42)
        await scheduler._job_memory_consolidation()
        mock_memory.count.assert_called_once()