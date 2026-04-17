"""Unit tests for HarnessAdapter."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentient.core.module_interface import ModuleStatus
from sentient.prajna.frontal.harness_adapter import (
    HarnessAdapter,
    TaskDelegation,
    TaskResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_event_bus():
    """Minimal event bus mock."""
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def adapter(mock_event_bus):
    """HarnessAdapter with test config."""
    config = {
        "harness": "claude_code",
        "command": ["claude", "--print"],
        "timeout_seconds": 60,
        "workdir": "/tmp/test_harness",
    }
    return HarnessAdapter(config, event_bus=mock_event_bus)


@pytest.fixture
def sample_task():
    """Minimal TaskDelegation for tests."""
    return TaskDelegation(
        task_id="test-task-001",
        goal="Write a test file",
        context={"repo": "example/repo", "branch": "main"},
        constraints={"max_time": 30},
        success_criteria=["file exists", "no lint errors"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Init tests
# ─────────────────────────────────────────────────────────────────────────────

def test_init_parses_harness_name(mock_event_bus):
    config = {"harness": "claw_code", "command": ["claw"]}
    adapter = HarnessAdapter(config, event_bus=mock_event_bus)
    assert adapter.harness_name == "claw_code"


def test_init_parses_command(mock_event_bus):
    config = {"harness": "claude", "command": ["claude", "--print", "--quiet"]}
    adapter = HarnessAdapter(config, event_bus=mock_event_bus)
    assert adapter.harness_command == ["claude", "--print", "--quiet"]


def test_init_parses_timeout(mock_event_bus):
    config = {"harness": "claude", "command": ["claude"], "timeout_seconds": 120}
    adapter = HarnessAdapter(config, event_bus=mock_event_bus)
    assert adapter.timeout_seconds == 120


def test_init_defaults_when_missing(mock_event_bus):
    adapter = HarnessAdapter({}, event_bus=mock_event_bus)
    assert adapter.harness_name == "claude_code"
    assert adapter.harness_command == ["claude"]
    assert adapter.timeout_seconds == 300
    assert adapter.workdir == "."
    assert adapter._completed_count == 0
    assert adapter._failed_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lifecycle tests (initialize / start)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_logs(adapter, caplog, mock_event_bus):
    with caplog.at_level("INFO"):
        await adapter.initialize()
    assert "Harness Adapter initialized" in caplog.text
    assert "claude_code" in caplog.text


@pytest.mark.asyncio
async def test_start_subscribes_and_sets_healthy(adapter, mock_event_bus):
    await adapter.start()
    mock_event_bus.subscribe.assert_called_once_with(
        "harness.delegate", adapter._handle_delegation
    )
    assert adapter._last_health_status == ModuleStatus.HEALTHY


@pytest.mark.asyncio
async def test_start_subscribes_to_correct_event(adapter, mock_event_bus):
    await adapter.start()
    call_args = mock_event_bus.subscribe.call_args
    assert call_args[0][0] == "harness.delegate"


@pytest.mark.asyncio
async def test_shutdown_is_idempotent(adapter):
    # Should not raise; existing implementation is a pass stub
    await adapter.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# 3. _handle_delegation tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_delegation_creates_task_delegation(adapter, mock_event_bus):
    payload = {
        "goal": "Analyze repo",
        "context": {"path": "/repo"},
        "constraints": {"timeout": 10},
        "success_criteria": ["done"],
    }
    with patch.object(adapter, "delegate_task", new_callable=AsyncMock) as mock_delegate:
        mock_delegate.return_value = TaskResult(
            task_id="ignored", success=True, output="ok", duration_seconds=1.0
        )
        await adapter._handle_delegation(payload)

    mock_delegate.assert_called_once()
    task_arg = mock_delegate.call_args[0][0]
    assert isinstance(task_arg, TaskDelegation)
    assert task_arg.goal == "Analyze repo"
    assert task_arg.context == {"path": "/repo"}


@pytest.mark.asyncio
async def test_handle_delegation_publishes_result(adapter, mock_event_bus):
    payload = {"goal": "Test publish"}
    result = TaskResult(
        task_id="abc-123", success=True, output="done", duration_seconds=2.5
    )
    with patch.object(adapter, "delegate_task", new_callable=AsyncMock) as mock_delegate:
        mock_delegate.return_value = result
        await adapter._handle_delegation(payload)

    # Verify the publish was called with the correct event and success/failure semantics
    mock_event_bus.publish.assert_called_once()
    call_args = mock_event_bus.publish.call_args
    assert call_args[0][0] == "harness.task.complete"
    published = call_args[0][1]
    assert published["success"] is True
    assert published["output"] == "done"
    assert published["error"] is None
    assert published["duration_seconds"] == 2.5
    assert "task_id" in published


@pytest.mark.asyncio
async def test_handle_delegation_publishes_failure_result(adapter, mock_event_bus):
    payload = {"goal": "Test failure publish"}
    result = TaskResult(
        task_id="fail-456", success=False, output="", error="crashed", duration_seconds=0.5
    )
    with patch.object(adapter, "delegate_task", new_callable=AsyncMock) as mock_delegate:
        mock_delegate.return_value = result
        await adapter._handle_delegation(payload)

    published = mock_event_bus.publish.call_args[0][1]
    assert published["success"] is False
    assert published["error"] == "crashed"


# ─────────────────────────────────────────────────────────────────────────────
# 4. delegate_task success
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_success(mock_exec, adapter, sample_task):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"all good", b""))
    process.returncode = 0
    mock_exec.return_value = process

    result = await adapter.delegate_task(sample_task)

    assert result.success is True
    assert result.output == "all good"
    assert result.error is None
    assert result.task_id == sample_task.task_id
    assert result.duration_seconds > 0
    assert adapter._completed_count == 1


@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_with_stderr_success(mock_exec, adapter, sample_task):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"output", b"warning: slow"))
    process.returncode = 0
    mock_exec.return_value = process

    result = await adapter.delegate_task(sample_task)

    assert result.success is True
    # stderr is ignored on success
    assert result.error is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. delegate_task failure (non-zero exit)
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_failure(mock_exec, adapter, sample_task):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"partial", b"error: failed"))
    process.returncode = 1
    mock_exec.return_value = process

    result = await adapter.delegate_task(sample_task)

    assert result.success is False
    assert result.output == "partial"
    assert result.error == "error: failed"
    assert adapter._failed_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 6. delegate_task timeout
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_timeout(mock_exec, adapter, sample_task):
    process = AsyncMock()
    process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_exec.return_value = process

    # Patch wait_for at the module level so the timeout fires
    with patch("sentient.prajna.frontal.harness_adapter.asyncio.wait_for", side_effect=asyncio.TimeoutError):
        result = await adapter.delegate_task(sample_task)

    assert result.success is False
    assert "timeout" in result.error
    assert adapter._failed_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 7. delegate_task FileNotFoundError
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_file_not_found(mock_exec, adapter, sample_task):
    mock_exec.side_effect = FileNotFoundError("claude: not found")

    result = await adapter.delegate_task(sample_task)

    assert result.success is False
    assert "not found" in result.error
    assert adapter._failed_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 8. delegate_task generic exception
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_task_generic_exception(mock_exec, adapter, sample_task, caplog):
    mock_exec.side_effect = RuntimeError("unexpected failure")

    with caplog.at_level("ERROR"):
        result = await adapter.delegate_task(sample_task)

    assert result.success is False
    assert result.error == "unexpected failure"
    assert adapter._failed_count == 1
    assert "Harness delegation error" in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# 9. _build_task_prompt with all fields
# ─────────────────────────────────────────────────────────────────────────────

def test_build_task_prompt_full(adapter, sample_task):
    prompt = adapter._build_task_prompt(sample_task)

    assert "GOAL: Write a test file" in prompt
    assert "CONTEXT:" in prompt
    assert '"repo"' in prompt  # JSON serialised context
    assert "CONSTRAINTS:" in prompt
    assert "  max_time: 30" in prompt
    assert "SUCCESS CRITERIA:" in prompt
    assert "  - file exists" in prompt
    assert "  - no lint errors" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 10. _build_task_prompt with empty context/constraints
# ─────────────────────────────────────────────────────────────────────────────

def test_build_task_prompt_empty_context_and_constraints(adapter):
    task = TaskDelegation(
        task_id="t2",
        goal="Simple goal",
        context={},
        constraints={},
        success_criteria=[],
    )
    prompt = adapter._build_task_prompt(task)

    assert "GOAL: Simple goal" in prompt
    assert "(none)" in prompt
    assert "CONSTRAINTS:" in prompt  # section header still present
    # No SUCCESS CRITERIA section when empty
    assert "SUCCESS CRITERIA:" not in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 11. health_pulse metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_health_pulse_includes_harness_name(adapter):
    pulse = adapter.health_pulse()
    assert pulse.metrics["harness"] == "claude_code"


def test_health_pulse_includes_counts(adapter):
    pulse = adapter.health_pulse()
    assert pulse.metrics["completed_count"] == 0
    assert pulse.metrics["failed_count"] == 0


def test_health_pulse_includes_active_tasks(adapter):
    pulse = adapter.health_pulse()
    assert pulse.metrics["active_tasks"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 12. Multiple delegations count tracking
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_increments_completed_count(mock_exec, adapter):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"out", b""))
    process.returncode = 0
    mock_exec.return_value = process

    task = TaskDelegation(task_id="t1", goal="g1", context={}, constraints={}, success_criteria=[])
    await adapter.delegate_task(task)
    assert adapter._completed_count == 1

    task2 = TaskDelegation(task_id="t2", goal="g2", context={}, constraints={}, success_criteria=[])
    await adapter.delegate_task(task2)
    assert adapter._completed_count == 2


@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_delegate_tracks_completed_and_failed_separately(mock_exec, adapter):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"out", b"err"))
    process.returncode = 0
    mock_exec.return_value = process

    task1 = TaskDelegation(task_id="t1", goal="g1", context={}, constraints={}, success_criteria=[])
    await adapter.delegate_task(task1)
    assert adapter._completed_count == 1
    assert adapter._failed_count == 0

    # Now simulate failure
    process.returncode = 1
    task2 = TaskDelegation(task_id="t2", goal="g2", context={}, constraints={}, success_criteria=[])
    await adapter.delegate_task(task2)
    assert adapter._completed_count == 1
    assert adapter._failed_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 13. Subprocess called with correct arguments
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_subprocess_called_with_configured_command(mock_exec, adapter, sample_task):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"out", b""))
    process.returncode = 0
    mock_exec.return_value = process

    await adapter.delegate_task(sample_task)

    mock_exec.assert_called_once()
    args, kwargs = mock_exec.call_args
    assert args == ("claude", "--print")
    assert kwargs["cwd"] == "/tmp/test_harness"
    assert kwargs["stdin"] == asyncio.subprocess.PIPE
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE


# ─────────────────────────────────────────────────────────────────────────────
# 14. health_pulse reflects live counts after delegations
# ─────────────────────────────────────────────────────────────────────────────

@patch("sentient.prajna.frontal.harness_adapter.asyncio.create_subprocess_exec")
@pytest.mark.asyncio
async def test_health_pulse_reflects_live_counts(mock_exec, adapter):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"out", b""))
    process.returncode = 0
    mock_exec.return_value = process

    for i in range(3):
        task = TaskDelegation(task_id=f"t{i}", goal=f"g{i}", context={}, constraints={}, success_criteria=[])
        await adapter.delegate_task(task)

    pulse = adapter.health_pulse()
    assert pulse.metrics["completed_count"] == 3
    assert pulse.metrics["failed_count"] == 0