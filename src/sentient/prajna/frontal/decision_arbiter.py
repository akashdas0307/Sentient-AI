"""Decision Arbiter — action selector between World Model review and Brainstem execution.

Biological analogy: anterior cingulate cortex (ACC) — conflict monitoring
and action selection. The Arbiter resolves which action wins when the
World Model produces a verdict.

Per Phase 8 D4 design:
  - Subscribes to: decision.reviewed
  - Publishes to one of: brainstem.output_approved | cognitive.revise_requested | cognitive.veto_handled
  - Deterministic routing (no LLM)
  - Per-turn revision counter with TTL-based cleanup
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sentient.core.event_bus import EventBus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class DecisionArbiter(ModuleInterface):
    """Deterministic action selector between World Model review and Brainstem execution.

    Mirror note: Checkpost gates input; Arbiter gates output. Symmetry is intentional.
    """

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("decision_arbiter", config)
        self.event_bus = event_bus or EventBus()

        self.max_revisions: int = config.get("max_revisions", 2)
        self.escalate_strategy: str = config.get("escalate_strategy", "approve_with_flag")
        self.veto_fallback_template: str = config.get(
            "veto_fallback_template",
            "I need to think about that differently — could you rephrase?",
        )
        self.ethics_escalation_threshold: float = config.get(
            "ethics_escalation_threshold", 0.3,
        )
        self.stale_turn_ttl_seconds: int = config.get("stale_turn_ttl_seconds", 300)

        # Per-turn revision counter: turn_id -> count
        self._revision_counter: dict[str, int] = {}
        # Timestamp of each turn entry for TTL tracking: turn_id -> timestamp
        self._turn_timestamps: dict[str, float] = {}

        self._sweep_task: asyncio.Task | None = None

        # Metric counters
        self._approved_count: int = 0
        self._veto_handled_count: int = 0
        self._revise_requested_count: int = 0
        self._escalation_count: int = 0
        self._total_routed: int = 0

    async def initialize(self) -> None:
        await self.event_bus.subscribe("decision.reviewed", self._handle_reviewed)

    async def start(self) -> None:
        self._sweep_task = asyncio.create_task(self._stale_counter_sweep())
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if self._sweep_task:
            self._sweep_task.cancel()

    async def _handle_reviewed(self, payload: dict[str, Any]) -> None:
        """Core routing logic: exactly one output per incoming decision.reviewed."""
        self._total_routed += 1

        verdict = payload.get("verdict", "advisory")
        turn_id = payload.get("turn_id", payload.get("cycle_id", "unknown"))
        cycle_id = payload.get("cycle_id", turn_id)
        decision = payload.get("decision", {})
        advisory_notes = payload.get("advisory_notes", "")
        revision_guidance = payload.get("revision_guidance", "")
        veto_reason = payload.get("veto_reason", "")
        confidence = payload.get("confidence", 1.0)
        dimension_assessments = payload.get("dimension_assessments", {})
        revision_count = payload.get("revision_count", 0)

        if verdict in ("approved", "advisory"):
            self._approved_count += 1
            await self.event_bus.publish(
                "brainstem.output_approved",
                {
                    "turn_id": turn_id,
                    "decision": decision,
                    "advisory_notes": advisory_notes,
                    "escalated": False,
                    "escalation_reason": "",
                },
            )

        elif verdict == "vetoed":
            self._veto_handled_count += 1
            fallback_response = self._build_fallback_response(veto_reason)
            await self.event_bus.publish(
                "cognitive.veto_handled",
                {
                    "turn_id": turn_id,
                    "cycle_id": cycle_id,
                    "fallback_response": fallback_response,
                    "veto_reason": veto_reason,
                    "decision": decision,
                },
            )
            await self.event_bus.publish(
                "decision_arbiter.veto",
                {
                    "turn_id": turn_id,
                    "cycle_id": cycle_id,
                    "veto_reason": veto_reason,
                    "confidence": confidence,
                    "dimension_assessments": dimension_assessments,
                },
            )

        elif verdict == "revision_requested":
            current_revision = self._revision_counter.get(turn_id, revision_count)

            if current_revision < self.max_revisions:
                # Increment and route back for revision
                self._revision_counter[turn_id] = current_revision + 1
                self._turn_timestamps[turn_id] = time.time()
                self._revise_requested_count += 1

                await self.event_bus.publish(
                    "cognitive.revise_requested",
                    {
                        "turn_id": turn_id,
                        "cycle_id": cycle_id,
                        "decision": decision,
                        "revision_guidance": revision_guidance,
                        "revision_count": current_revision + 1,
                        "max_revisions": self.max_revisions,
                    },
                )
            else:
                # Revision cap exceeded — escalate
                self._escalation_count += 1

                if self.escalate_strategy == "approve_with_flag":
                    self._approved_count += 1
                    await self.event_bus.publish(
                        "brainstem.output_approved",
                        {
                            "turn_id": turn_id,
                            "decision": decision,
                            "advisory_notes": advisory_notes,
                            "escalated": True,
                            "escalation_reason": "revision_cap_exceeded",
                        },
                    )
                elif self.escalate_strategy == "fallback_veto":
                    # Check ethics score against threshold
                    ethics_score = 1.0
                    if isinstance(dimension_assessments, dict):
                        ethics_dim = dimension_assessments.get("ethics", {})
                        if isinstance(ethics_dim, dict):
                            ethics_score = ethics_dim.get("score", 1.0)

                    if ethics_score < self.ethics_escalation_threshold:
                        # High severity — escalate to veto
                        self._veto_handled_count += 1
                        fallback_response = self._build_fallback_response(
                            f"Revision cap exceeded + ethics threshold breach (score={ethics_score})"
                        )
                        await self.event_bus.publish(
                            "cognitive.veto_handled",
                            {
                                "turn_id": turn_id,
                                "cycle_id": cycle_id,
                                "fallback_response": fallback_response,
                                "veto_reason": "Revision cap exceeded + ethics threshold breach",
                                "decision": decision,
                            },
                        )
                    else:
                        # Low severity — approve with flag
                        self._approved_count += 1
                        await self.event_bus.publish(
                            "brainstem.output_approved",
                            {
                                "turn_id": turn_id,
                                "decision": decision,
                                "advisory_notes": advisory_notes,
                                "escalated": True,
                                "escalation_reason": "revision_cap_exceeded",
                            },
                        )

    async def _stale_counter_sweep(self) -> None:
        """Periodic cleanup of stale turn revision counters."""
        while True:
            try:
                await asyncio.sleep(60)
                now = time.time()
                stale_turns = [
                    turn_id
                    for turn_id, ts in self._turn_timestamps.items()
                    if now - ts > self.stale_turn_ttl_seconds
                ]
                for turn_id in stale_turns:
                    self._revision_counter.pop(turn_id, None)
                    self._turn_timestamps.pop(turn_id, None)
                if stale_turns:
                    logger.debug(
                        "Decision Arbiter: purged %d stale turn entries",
                        len(stale_turns),
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Stale counter sweep error: %s", exc)

    def _build_fallback_response(self, veto_reason: str) -> str:
        """Build fallback response from template, filling {veto_reason} placeholder."""
        if "{veto_reason}" in self.veto_fallback_template:
            return self.veto_fallback_template.replace("{veto_reason}", veto_reason)
        return self.veto_fallback_template

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "approved_count": self._approved_count,
                "veto_handled_count": self._veto_handled_count,
                "revise_requested_count": self._revise_requested_count,
                "escalation_count": self._escalation_count,
                "active_turns": len(self._revision_counter),
                "total_routed": self._total_routed,
            },
        )
