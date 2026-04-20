"""Agent Harness Adapter — delegates complex execution to existing harnesses.

Per DD-003, we don't build an execution engine. We wrap existing harnesses
(Claw Code, Claude Code, Hermes) and let them handle complex multi-step
tasks autonomously.

The Cognitive Core decides WHAT and WHY. The harness handles HOW.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskDelegation:
    """A task delegated to the harness."""
    task_id: str
    goal: str
    context: dict[str, Any]
    constraints: dict[str, Any]
    success_criteria: list[str]
    delegated_at: float = field(default_factory=time.time)


@dataclass
class TaskResult:
    """Result returned from the harness."""
    task_id: str
    success: bool
    output: str
    error: str | None = None
    duration_seconds: float = 0.0
    completed_at: float = field(default_factory=time.time)


class HarnessAdapter(ModuleInterface):
    """Wraps an external agent harness as a delegation target.

    For MVS, supports Claude Code or Claw Code via subprocess. The CLI
    is invoked with the task description; output is captured and parsed.
    """

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("harness_adapter", config)
        self.event_bus = event_bus or get_event_bus()

        # Which harness to use (configurable)
        self.harness_name = config.get("harness", "claude_code")
        self.harness_command = config.get("command", ["claude"])
        self.timeout_seconds = config.get("timeout_seconds", 300)
        self.workdir = config.get("workdir", ".")
        self.enabled = config.get("enabled", True)
        self.workspace_dir = config.get("workspace_dir", self.workdir)

        # Validate workspace_dir is absolute
        if not os.path.isabs(self.workspace_dir):
            self.workspace_dir = os.path.abspath(self.workspace_dir)

        # Rate limit to 1 concurrent task (MVS constraint)
        self._semaphore = asyncio.Semaphore(1)
        # Will be set during initialize()
        self._available: bool | None = None
        self._shutdown_flag = False

        self._active_tasks: dict[str, TaskDelegation] = {}
        self._completed_count = 0
        self._failed_count = 0

    async def initialize(self) -> None:
        # Verify harness is available on PATH
        which_result = shutil.which(self.harness_command[0])
        self._available = bool(which_result)
        if not self._available:
            logger.warning(
                "Harness command '%s' not found on PATH — delegation will return unavailable error",
                self.harness_command[0],
            )
        logger.info("Harness Adapter initialized (harness=%s)", self.harness_name)

    async def start(self) -> None:
        # Subscribe to both harness.delegate and decide.delegate
        await self.event_bus.subscribe("harness.delegate", self._handle_delegation)
        await self.event_bus.subscribe("decide.delegate", self._handle_delegation)
        # Set status based on enabled and availability
        if self.enabled and self._available:
            self.set_status(ModuleStatus.HEALTHY)
        elif self.enabled and not self._available:
            self.set_status(ModuleStatus.DEGRADED)
        else:
            self.set_status(ModuleStatus.DEGRADED)

    async def shutdown(self) -> None:
        # Signal no new delegations should be accepted
        self._shutdown_flag = True

    async def _handle_delegation(self, payload: dict[str, Any]) -> None:
        """Receive a delegation request from the Cognitive Core."""
        # Early exit checks
        if not self.enabled:
            await self.event_bus.publish(
                "harness.task.complete",
                {
                    "task_id": payload.get("task_id", str(uuid.uuid4())),
                    "success": False,
                    "output": "",
                    "error": "Harness adapter disabled by config",
                    "duration_seconds": 0.0,
                },
            )
            return

        if not self._available:
            await self.event_bus.publish(
                "harness.task.complete",
                {
                    "task_id": payload.get("task_id", str(uuid.uuid4())),
                    "success": False,
                    "output": "",
                    "error": f"Harness unavailable: command '{self.harness_command[0]}' not found on PATH",
                    "duration_seconds": 0.0,
                },
            )
            return

        if self._shutdown_flag:
            return

        async with self._semaphore:
            task = TaskDelegation(
                task_id=str(uuid.uuid4()),
                goal=payload.get("goal", ""),
                context=payload.get("context", {}),
                constraints=payload.get("constraints", {}),
                success_criteria=payload.get("success_criteria", []),
            )
            self._active_tasks[task.task_id] = task
            result = await self.delegate_task(task)
            del self._active_tasks[task.task_id]

            await self.event_bus.publish(
                "harness.task.complete",
                {
                    "task_id": task.task_id,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "duration_seconds": result.duration_seconds,
                },
            )

    async def delegate_task(self, task: TaskDelegation) -> TaskResult:
        """Spawn the harness CLI to execute the task."""
        prompt = self._build_task_prompt(task)
        start = time.time()

        try:
            # Build environment with HARNESS_WORKSPACE safety var
            env = os.environ.copy()
            env["HARNESS_WORKSPACE"] = self.workspace_dir

            # Run the harness CLI as a subprocess
            process = await asyncio.create_subprocess_exec(
                *self.harness_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_dir,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode()),
                timeout=self.timeout_seconds,
            )

            duration = time.time() - start
            success = process.returncode == 0

            if success:
                self._completed_count += 1
            else:
                self._failed_count += 1

            return TaskResult(
                task_id=task.task_id,
                success=success,
                output=stdout.decode("utf-8", errors="replace"),
                error=stderr.decode("utf-8", errors="replace") if not success else None,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            self._failed_count += 1
            return TaskResult(
                task_id=task.task_id,
                success=False,
                output="",
                error=f"Task exceeded {self.timeout_seconds}s timeout",
                duration_seconds=time.time() - start,
            )
        except FileNotFoundError:
            self._failed_count += 1
            return TaskResult(
                task_id=task.task_id,
                success=False,
                output="",
                error=f"Harness command not found: {self.harness_command[0]}",
                duration_seconds=time.time() - start,
            )
        except Exception as exc:
            self._failed_count += 1
            logger.exception("Harness delegation error: %s", exc)
            return TaskResult(
                task_id=task.task_id,
                success=False,
                output="",
                error=str(exc),
                duration_seconds=time.time() - start,
            )

    def _build_task_prompt(self, task: TaskDelegation) -> str:
        """Build the prompt to send to the harness CLI."""
        sections = [
            f"GOAL: {task.goal}",
            "",
            "CONTEXT:",
            json.dumps(task.context, indent=2) if task.context else "(none)",
            "",
            "CONSTRAINTS:",
        ]
        for k, v in task.constraints.items():
            sections.append(f"  {k}: {v}")
        if task.success_criteria:
            sections.append("")
            sections.append("SUCCESS CRITERIA:")
            for c in task.success_criteria:
                sections.append(f"  - {c}")
        return "\n".join(sections)

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "harness": self.harness_name,
                "completed_count": self._completed_count,
                "failed_count": self._failed_count,
                "active_tasks": len(self._active_tasks),
                "enabled": self.enabled,
                "available": self._available if self._available is not None else False,
            },
        )
