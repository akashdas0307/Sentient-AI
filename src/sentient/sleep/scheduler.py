"""Sleep Scheduler — four-stage sleep with adaptive duration.

Per ARCHITECTURE.md §3.5 and DD-014, DD-027:
  - Four stages: Settling, Maintenance, Deep Consolidation, Pre-Wake
  - Adaptive duration: 6-12 hours based on workload
  - Interruptibility varies by stage
  - Sleepwalking mode for non-emergency inputs during deep sleep
  - Checkpoint save for emergency wake from deep consolidation
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class SleepStage(Enum):
    AWAKE = "awake"
    SETTLING = "settling"
    MAINTENANCE = "maintenance"
    DEEP_CONSOLIDATION = "deep_consolidation"
    PRE_WAKE = "pre_wake"


class SleepScheduler(ModuleInterface):
    """Manages the sleep/wake cycle."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle_manager: Any,   # LifecycleManager
        memory: Any | None = None,
        consolidation_engine: Any | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("sleep_scheduler", config)
        self.event_bus = event_bus or get_event_bus()
        self.lifecycle = lifecycle_manager
        self.memory = memory
        self.consolidation_engine = consolidation_engine

        self.min_hours = config.get("duration", {}).get("min_hours", 6)
        self.max_hours = config.get("duration", {}).get("max_hours", 12)
        self.settling_minutes = config.get("stages", {}).get("settling_minutes", 45)
        self.pre_wake_minutes = config.get("stages", {}).get("pre_wake_minutes", 45)
        self.consolidation_enabled = config.get("consolidation_enabled", True)

        circadian = config.get("default_circadian", {})
        self.sleep_hour = circadian.get("sleep_hour", 23)
        self.wake_hour = circadian.get("wake_hour", 7)

        self.current_stage = SleepStage.AWAKE
        self._stage_entered_at: float = time.time()
        self._current_sleep_duration_seconds: float = 0.0
        self._checkpoint: dict[str, Any] = {}
        self._wake_up_inbox: list[Any] = []
        self._sleep_cycle_count = 0
        self._scheduler_task: asyncio.Task | None = None
        self._current_sleep_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        await self.event_bus.subscribe("health.escalation", self._handle_emergency)
        await self.event_bus.subscribe("input.received", self._handle_input_during_sleep)
        logger.info("Sleep Scheduler initialized")

    async def start(self) -> None:
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._current_sleep_task:
            self._current_sleep_task.cancel()

    # === Scheduling ===

    async def _schedule_loop(self) -> None:
        """Main scheduler — checks whether it's time to sleep."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                if self.current_stage == SleepStage.AWAKE:
                    if self._is_sleep_time():
                        await self.enter_sleep()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Sleep schedule loop error: %s", exc)

    def _is_sleep_time(self) -> bool:
        """Check whether it's time to begin sleep."""
        now = datetime.now()
        hour = now.hour
        # Sleep window: sleep_hour to wake_hour (crossing midnight)
        if self.sleep_hour < self.wake_hour:
            return self.sleep_hour <= hour < self.wake_hour
        else:
            return hour >= self.sleep_hour or hour < self.wake_hour

    async def enter_sleep(self, requested_hours: float | None = None) -> None:
        """Transition through the four sleep stages."""
        if self.current_stage != SleepStage.AWAKE:
            logger.warning("Already sleeping — ignoring duplicate enter_sleep")
            return

        self._sleep_cycle_count += 1
        total_hours = self._estimate_needed_duration() if requested_hours is None else requested_hours
        total_hours = max(self.min_hours, min(self.max_hours, total_hours))
        self._current_sleep_duration_seconds = total_hours * 3600

        logger.info(
            "Sleep cycle #%d starting — estimated duration: %.1f hours",
            self._sleep_cycle_count, total_hours,
        )

        # Run the sleep sequence as a task so it can be cancelled for emergency
        self._current_sleep_task = asyncio.create_task(
            self._sleep_sequence(total_hours)
        )

    async def _sleep_sequence(self, total_hours: float) -> None:
        """Execute the four-stage sleep sequence."""
        try:
            # Stage 1: Settling
            await self._enter_stage(SleepStage.SETTLING)
            await self._run_settling()

            # Stage 2: Maintenance
            maintenance_minutes = 60 + (self._sleep_cycle_count % 60)  # 60-120
            await self._enter_stage(SleepStage.MAINTENANCE)
            await self._run_maintenance(maintenance_minutes)

            # Stage 3: Deep Consolidation — the heart of sleep
            deep_minutes = (total_hours * 60) - self.settling_minutes - maintenance_minutes - self.pre_wake_minutes
            deep_minutes = max(30, deep_minutes)
            await self._enter_stage(SleepStage.DEEP_CONSOLIDATION)
            await self._run_deep_consolidation(deep_minutes)

            # Stage 4: Pre-Wake
            await self._enter_stage(SleepStage.PRE_WAKE)
            await self._run_pre_wake()

            # Fully wake
            await self._wake_up()

        except asyncio.CancelledError:
            logger.info("Sleep cycle interrupted")
            raise

    async def _enter_stage(self, stage: SleepStage) -> None:
        """Transition into a new sleep stage."""
        self.current_stage = stage
        self._stage_entered_at = time.time()
        await self.event_bus.publish(
            "sleep.stage.transition",
            {"stage": stage.value, "cycle": self._sleep_cycle_count},
        )
        logger.info("Sleep: entered stage %s", stage.value)

    # === Stage implementations ===

    async def _run_settling(self) -> None:
        """Stage 1: wind down, save state, drain queue."""
        # Give active work time to complete naturally
        await asyncio.sleep(self.settling_minutes * 60)

    async def _run_maintenance(self, minutes: float) -> None:
        """Stage 2: database optimization, logs, health diagnostic."""
        await self.lifecycle.pause_for_sleep()

        # Memory maintenance
        if self.memory:
            # MVS: just logs. Phase 2+ runs actual DB optimization.
            logger.info("Sleep maintenance: running memory optimization")

        await self.event_bus.publish(
            "sleep.maintenance.running",
            {"cycle": self._sleep_cycle_count},
        )

        # Wait for the full maintenance window (or until interrupted)
        await asyncio.sleep(minutes * 60)

    async def _run_deep_consolidation(self, minutes: float) -> None:
        """Stage 3: the heart of sleep — memory consolidation.

        Per ARCHITECTURE.md §3.5, seven jobs run here:
          1. Memory consolidation (progressive summarization)
          2. Contradiction resolution
          3. Procedural memory refinement
          4. World Model Journal calibration
          5. Identity drift detection
          6. Trait discovery
          7. Offspring evaluation (Phase 3)

        MVS: runs ConsolidationEngine for job 1. Others are stubs.
        """
        await self.event_bus.publish(
            "sleep.deep_consolidation.start",
            {"cycle": self._sleep_cycle_count},
        )

        # Run consolidation engine if available and enabled
        if self.consolidation_engine and self.consolidation_enabled:
            try:
                result = await self.consolidation_engine.consolidate_cycle()
                logger.info(
                    "Consolidation completed: %s (facts=%s, patterns=%s)",
                    result.get("status"),
                    result.get("facts_extracted", 0),
                    result.get("patterns_extracted", 0),
                )
            except Exception as exc:
                logger.exception("Consolidation engine error: %s", exc)
        else:
            # Fallback: run stub consolidation for backward compatibility
            await self._job_memory_consolidation()
        # await self._job_contradiction_resolution()    # Phase 2
        # await self._job_procedural_refinement()       # Phase 2
        # await self._job_world_model_calibration()     # Phase 2
        # await self._job_identity_drift_detection()    # Phase 2
        # await self._job_trait_discovery()             # Phase 2
        # await self._job_offspring_evaluation()        # Phase 3

        # Spend the rest of the window in light consolidation sleep
        consolidation_runtime = minutes * 60
        await asyncio.sleep(consolidation_runtime)

    async def _job_memory_consolidation(self) -> None:
        """Job 1: progressive summarization of episodic memories.

        Per ARCHITECTURE.md §3.5, compresses recent episodic memories into
        daily → weekly → monthly → quarterly summaries.

        MVS: logs the work. Phase 2+ implements actual summarization LLM calls.
        """
        if not self.memory:
            return
        try:
            count = await self.memory.count()
            logger.info("Sleep: memory consolidation — %d memories in store", count)
        except Exception as exc:
            logger.exception("Memory consolidation error: %s", exc)

    async def _run_pre_wake(self) -> None:
        """Stage 4: compile handoff package, reinitialize."""
        await self.lifecycle.resume_from_sleep()

        # Build handoff package
        handoff = {
            "cycle": self._sleep_cycle_count,
            "duration_hours": self._current_sleep_duration_seconds / 3600,
            "jobs_completed": ["memory_consolidation"],
            "wake_up_inbox_count": len(self._wake_up_inbox),
            "pending_trait_candidates": [],
            "offspring_promotion_proposals": [],
            "incomplete_jobs": [],
        }

        await self.event_bus.publish("sleep.handoff.ready", {"handoff": handoff})

        # Wait for pre-wake window
        await asyncio.sleep(self.pre_wake_minutes * 60)

    async def _wake_up(self) -> None:
        """Transition to AWAKE state."""
        self.current_stage = SleepStage.AWAKE
        self._stage_entered_at = time.time()

        await self.event_bus.publish(
            "sleep.wake",
            {
                "cycle": self._sleep_cycle_count,
                "wake_up_inbox_count": len(self._wake_up_inbox),
            },
        )

        # Deliver wake-up inbox items to Queue Zone
        # (simplified — in full implementation, create envelopes for each)
        self._wake_up_inbox.clear()

        logger.info("Sleep cycle #%d complete — system awake", self._sleep_cycle_count)

    # === Duration estimation ===

    def _estimate_needed_duration(self) -> float:
        """Estimate required sleep duration based on workload.

        Per ARCHITECTURE.md §3.5, factors include memory count, contradictions,
        offspring tests, etc.
        """
        base_hours = self.min_hours
        # MVS: simple heuristic — add 1 hour per 200 new memories since last cycle
        # Phase 2+ expands this with real workload estimation
        return base_hours

    # === Interruption handling ===

    async def _handle_emergency(self, payload: dict[str, Any]) -> None:
        """Handle emergency wake from any stage."""
        if self.current_stage == SleepStage.AWAKE:
            return
        severity = payload.get("severity", "")
        if severity in ("CRITICAL", "SYSTEM_DOWN"):
            logger.warning("Emergency wake triggered: %s", severity)
            await self._emergency_wake()

    async def _emergency_wake(self) -> None:
        """Checkpoint + compressed pre-wake + full wake."""
        if self.current_stage == SleepStage.DEEP_CONSOLIDATION:
            # Save checkpoint of current consolidation progress
            self._checkpoint = {
                "stage": self.current_stage.value,
                "interrupted_at": time.time(),
            }

        # Cancel normal sleep sequence
        if self._current_sleep_task and not self._current_sleep_task.done():
            self._current_sleep_task.cancel()

        await self._wake_up()

    async def _handle_input_during_sleep(self, payload: dict[str, Any]) -> None:
        """Handle inputs that arrive while asleep.

        Per DD-027, three-level response:
          - CRITICAL → full wake
          - Important but not emergency → sleepwalking mode
          - Routine → ignore, log to wake-up inbox
        """
        if self.current_stage == SleepStage.AWAKE:
            return
        priority = payload.get("priority")
        if priority == 1:   # Tier 1
            await self._emergency_wake()
        elif priority == 2:   # Tier 2 — sleepwalking
            # Store for morning, send brief acknowledgment via Brainstem reflex
            self._wake_up_inbox.append(payload)
            # In full implementation, send ack through Brainstem reflex system
        else:
            # Routine — silent log
            self._wake_up_inbox.append(payload)

    # === Health ===

    def health_pulse(self) -> HealthPulse:
        stage_duration = time.time() - self._stage_entered_at
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "current_stage": self.current_stage.value,
                "stage_duration_seconds": round(stage_duration, 1),
                "sleep_cycle_count": self._sleep_cycle_count,
                "wake_up_inbox_size": len(self._wake_up_inbox),
                "checkpoint_present": bool(self._checkpoint),
            },
        )
