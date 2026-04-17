"""Sleep scheduler test fixtures with proper teardown to prevent RAM leaks.

Each scheduler test may create background asyncio tasks. This conftest ensures:
  1. Scheduler tasks are cancelled after each test
  2. References are released and GC runs (reclaims memory)
  3. Mock objects are cleaned up (reset_mock + del)
"""
from __future__ import annotations

import gc

import pytest
from unittest.mock import AsyncMock, MagicMock

from sentient.sleep.scheduler import SleepScheduler


@pytest.fixture
def mock_event_bus():
    """Mock EventBus with async publish/subscribe/unsubscribe."""
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
    """Base config dict for SleepScheduler."""
    return {
        "duration": {"min_hours": 6, "max_hours": 12},
        "stages": {"settling_minutes": 5, "pre_wake_minutes": 5},
        "default_circadian": {"sleep_hour": 22, "wake_hour": 7},
    }


@pytest.fixture
def scheduler(mock_event_bus, mock_lifecycle, mock_memory, base_config):
    """SleepScheduler instance. Tests that start async tasks should cancel them."""
    s = SleepScheduler(base_config, mock_lifecycle, mock_memory, mock_event_bus)
    yield s
    # Cancel any tasks the scheduler created
    for attr in ("_scheduler_task", "_current_sleep_task"):
        task = getattr(s, attr, None)
        if task is not None and not task.done():
            task.cancel()
    del s
    gc.collect()