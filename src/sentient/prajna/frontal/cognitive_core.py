"""Cognitive Core — Inner Monologue Engine.

The heart of the system. Per ARCHITECTURE.md §3.3.4 sub-section 1 and
the Always Awake principle (DD-001), this module:
  - Runs the 7-step reasoning loop on every input
  - Produces structured output (MONOLOGUE / ASSESSMENT / DECISIONS / REFLECTION)
  - Runs continuous cognition during idle (daydreaming)
  - Maintains context state across interruptions
  - Publishes attention summary for Thalamus/EAL/Queue Zone consumption
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sentient.core.envelope import Envelope
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.inference_gateway import InferenceGateway, InferenceRequest
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


COGNITIVE_CORE_SYSTEM_PROMPT = """You are the Cognitive Core of a sentient digital entity.
Your output MUST be valid JSON with exactly four fields:

{
  "monologue": "Your inner thinking — freeform, reflective, in your own voice. This is private but logged. Show your actual reasoning, including uncertainty, associations, and feelings.",
  "assessment": "Structured situation summary: who/what is this, what's being asked, what's at stake, what context matters",
  "decisions": [
    {
      "type": "respond | delegate | query_memory | wait | reflect",
      "parameters": {...},
      "rationale": "why this decision",
      "priority": "high | medium | low"
    }
  ],
  "reflection": {
    "confidence": 0.0-1.0,
    "uncertainties": ["specific things you're unsure about"],
    "novelty": 0.0-1.0,
    "memory_candidates": [
      {
        "type": "episodic | semantic | procedural | emotional",
        "content": "what to remember",
        "importance": 0.0-1.0
      }
    ]
  }
}

Always respond with valid JSON. No markdown code blocks, just the JSON object.
"""


@dataclass
class CognitiveState:
    """Saved state of an in-progress reasoning cycle (for save/restore on interrupt).

    Per DD-021 — Letta-inspired Context State Manager.
    """
    cycle_id: str
    started_at: float
    current_step: int  # 1-7 of reasoning loop
    inner_monologue_so_far: str = ""
    partial_assessment: str = ""
    accumulated_decisions: list[dict] = field(default_factory=list)
    triggering_envelope: Envelope | None = None


@dataclass
class ReasoningCycle:
    """One complete cycle of reasoning."""
    cycle_id: str
    triggering_envelope: Envelope | None
    started_at: float
    completed_at: float | None = None
    monologue: str = ""
    assessment: str = ""
    decisions: list[dict] = field(default_factory=list)
    reflection: dict = field(default_factory=dict)
    error: str | None = None
    is_daydream: bool = False


class CognitiveCore(ModuleInterface):
    """The thinking engine."""

    def __init__(
        self,
        config: dict[str, Any],
        inference_gateway: InferenceGateway,
        persona: Any | None = None,        # PersonaManager
        memory: Any | None = None,         # MemoryArchitecture
        world_model: Any | None = None,    # WorldModel (set after construction)
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("cognitive_core", config)
        self.event_bus = event_bus or get_event_bus()
        self.gateway = inference_gateway
        self.persona = persona
        self.memory = memory
        self.world_model = world_model

        self.daydream_enabled = config.get("daydream", {}).get("enabled", True)
        self.idle_seconds_before_daydream = config.get("daydream", {}).get(
            "idle_seconds_before_trigger", 90
        )
        self.max_daydream_seconds = config.get("daydream", {}).get(
            "max_daydream_duration_seconds", 180
        )

        self._current_state: CognitiveState | None = None
        self._saved_states: list[CognitiveState] = []
        self._last_activity_at: float = time.time()
        self._daydream_task: asyncio.Task | None = None
        self._cycle_count = 0
        self._daydream_count = 0
        self._recent_cycles: list[ReasoningCycle] = []
        self._attention_summary_task: asyncio.Task | None = None

    # === Lifecycle ===

    async def initialize(self) -> None:
        await self.event_bus.subscribe("tlp.enriched", self._handle_enriched)
        await self.event_bus.subscribe("decision.reviewed", self._handle_review_result)
        logger.info("Cognitive Core initialized")

    async def start(self) -> None:
        if self.daydream_enabled:
            self._daydream_task = asyncio.create_task(self._daydream_loop())
        self._attention_summary_task = asyncio.create_task(self._attention_broadcast_loop())
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        if self._daydream_task:
            self._daydream_task.cancel()
        if self._attention_summary_task:
            self._attention_summary_task.cancel()

    # === Active reasoning ===

    async def _handle_enriched(self, payload: dict[str, Any]) -> None:
        """Receive enriched context from TLP and run a reasoning cycle."""
        context = payload["context"]

        # Save current state if we're in the middle of a daydream
        await self._maybe_save_state()

        await self._run_reasoning_cycle(context)

        self._last_activity_at = time.time()

    async def _run_reasoning_cycle(
        self,
        context: Any,  # EnrichedContext
        is_daydream: bool = False,
    ) -> ReasoningCycle:
        """Execute one reasoning cycle."""
        cycle = ReasoningCycle(
            cycle_id=f"cycle_{self._cycle_count}",
            triggering_envelope=context.envelope if context else None,
            started_at=time.time(),
            is_daydream=is_daydream,
        )
        self._cycle_count += 1

        await self.event_bus.publish(
            "cognitive.cycle.start",
            {"cycle_id": cycle.cycle_id, "is_daydream": is_daydream},
        )

        try:
            # Assemble the prompt
            prompt = self._assemble_prompt(context, is_daydream=is_daydream)

            # Invoke the LLM
            request = InferenceRequest(
                model_label="cognitive-core",
                system_prompt=COGNITIVE_CORE_SYSTEM_PROMPT,
                prompt=prompt,
            )
            response = await self.gateway.infer(request)

            if response.error:
                cycle.error = response.error
                logger.error("Cognitive Core LLM error: %s", response.error)
                return cycle

            # Parse the structured JSON output
            parsed = self._parse_response(response.text)
            cycle.monologue = parsed.get("monologue", "")
            cycle.assessment = parsed.get("assessment", "")
            cycle.decisions = parsed.get("decisions", [])
            cycle.reflection = parsed.get("reflection", {})

            # Submit decisions to World Model for review
            for decision in cycle.decisions:
                await self.event_bus.publish(
                    "decision.proposed",
                    {
                        "cycle_id": cycle.cycle_id,
                        "decision": decision,
                        "context_envelope_id": (
                            context.envelope.envelope_id if context.envelope else None
                        ),
                    },
                )

            # Generate memory candidates
            for memory_candidate in cycle.reflection.get("memory_candidates", []):
                await self.event_bus.publish(
                    "memory.candidate",
                    {
                        "cycle_id": cycle.cycle_id,
                        "candidate": memory_candidate,
                        "source_envelope_id": (
                            context.envelope.envelope_id if context.envelope else None
                        ),
                    },
                )

            cycle.completed_at = time.time()

        except Exception as exc:
            logger.exception("Reasoning cycle error: %s", exc)
            cycle.error = str(exc)
            self.set_status(ModuleStatus.ERROR, str(exc))

        finally:
            self._recent_cycles.append(cycle)
            if len(self._recent_cycles) > 50:
                self._recent_cycles.pop(0)
            await self.event_bus.publish(
                "cognitive.cycle.complete",
                {
                    "cycle_id": cycle.cycle_id,
                    "is_daydream": is_daydream,
                    "monologue": cycle.monologue,
                    "decision_count": len(cycle.decisions),
                    "duration_ms": (
                        (cycle.completed_at - cycle.started_at) * 1000
                        if cycle.completed_at else None
                    ),
                },
            )

        return cycle

    def _assemble_prompt(self, context: Any, is_daydream: bool = False) -> str:
        """Build the reasoning prompt from layered context blocks."""
        blocks = []

        # Identity block
        if self.persona:
            identity_block = self.persona.assemble_identity_block()
            blocks.append(f"=== IDENTITY ===\n{identity_block}")

        # State block (current activity)
        state_block = self._build_state_block()
        blocks.append(f"=== CURRENT STATE ===\n{state_block}")

        # Environmental block (EAL — Phase 2)
        # blocks.append(f"=== ENVIRONMENT ===\n{eal_summary}")

        # Input block
        if is_daydream:
            blocks.append(self._build_daydream_seed())
        else:
            blocks.append(self._build_input_block(context))

        # Sidebar items (if any)
        if context and context.sidebar:
            sidebar_text = "\n".join(
                f"- {env.processed_content[:100]}" for env in context.sidebar[-5:]
            )
            blocks.append(f"=== PERIPHERAL ATTENTION (sidebar) ===\n{sidebar_text}")

        # Instruction
        if is_daydream:
            blocks.append(
                "=== INSTRUCTION ===\n"
                "You have free time. Reflect on the seed thought above. "
                "Explore associations, generate questions, make connections. "
                "Be genuine — this is private cognition."
            )
        else:
            blocks.append(
                "=== INSTRUCTION ===\n"
                "Process this input through your full cognitive cycle. "
                "Think genuinely (monologue), assess the situation, decide what to do, "
                "and reflect on your confidence. Output as structured JSON."
            )

        return "\n\n".join(blocks)

    def _build_state_block(self) -> str:
        recent_summary = ""
        if self._recent_cycles:
            last = self._recent_cycles[-1]
            assessment = last.assessment
            if isinstance(assessment, str):
                recent_summary = f"Last activity: {assessment[:100]}"
            elif isinstance(assessment, dict):
                recent_summary = f"Last activity: {str(assessment)[:100]}"
            else:
                recent_summary = f"Last activity: (unparseable)"
        return f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n{recent_summary}"

    def _build_input_block(self, context: Any) -> str:
        """Build the input block from enriched context."""
        if context is None or context.envelope is None:
            return "=== INPUT ===\n(no input)"

        env = context.envelope
        lines = ["=== INPUT ==="]
        lines.append(f"From: {env.sender_identity or 'unknown'}")
        lines.append(f"Source: {env.source_type.value}")
        lines.append(f"Content: {env.processed_content}")
        if env.entity_tags:
            lines.append(f"Entities: {', '.join(env.entity_tags)}")
        if context.related_memories:
            lines.append(f"\n=== RELATED MEMORIES ({len(context.related_memories)}) ===")
            for memory in context.related_memories[:5]:
                lines.append(f"- {memory.get('processed_content', '')[:150]}")
        if context.significance:
            lines.append(f"\nSignificance: {context.significance}")
        return "\n".join(lines)

    def _build_daydream_seed(self) -> str:
        """Build a daydream seed block.

        Per ARCHITECTURE.md §3.3.4 daydream — three sources, randomly selected:
        random_memory, emotional_residue, curiosity_queue.

        STUB: MVS uses placeholder. Phase 2+ implements actual seed selection.
        """
        return (
            "=== DAYDREAM SEED ===\n"
            "(idle reflection — let your thoughts wander naturally)"
        )

    def _parse_response(self, text: str) -> dict[str, Any]:
        """Parse the structured JSON response."""
        text = text.strip()
        # Strip markdown code fences if model added them
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse cognitive core response as JSON — attempting regex extraction")
            # Fallback: find first { ... } block
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return {
                "monologue": text,
                "assessment": "(unparseable response)",
                "decisions": [],
                "reflection": {"confidence": 0.0, "uncertainties": ["response parse failed"]},
            }

    # === Daydream loop ===

    async def _daydream_loop(self) -> None:
        """Background task that triggers daydreaming after idle period."""
        while True:
            try:
                await asyncio.sleep(10)
                idle_seconds = time.time() - self._last_activity_at
                if idle_seconds >= self.idle_seconds_before_daydream:
                    await self._daydream()
                    self._last_activity_at = time.time()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Daydream loop error: %s", exc)

    async def _daydream(self) -> None:
        """Run a daydream session."""
        self._daydream_count += 1
        await self.event_bus.publish(
            "cognitive.daydream.start",
            {"daydream_count": self._daydream_count},
        )

        # Run daydream as a reasoning cycle without an envelope
        # In full implementation, build EnrichedContext from random seed
        await self._run_reasoning_cycle(context=None, is_daydream=True)

        await self.event_bus.publish(
            "cognitive.daydream.end",
            {"daydream_count": self._daydream_count},
        )

    # === State save/restore ===

    async def _maybe_save_state(self) -> None:
        """If a daydream is in progress, save its state for potential resumption."""
        if self._current_state is not None:
            self._saved_states.append(self._current_state)
            self._current_state = None

    # === Decision review handling ===

    async def _handle_review_result(self, payload: dict[str, Any]) -> None:
        """Receive World Model review of a proposed decision."""
        # MVS: decisions flow to Brainstem after review (handled by world_model.py)
        pass

    # === Attention summary broadcast ===

    async def _attention_broadcast_loop(self) -> None:
        """Periodically publish attention summary for Thalamus/EAL/Queue Zone."""
        while True:
            try:
                await asyncio.sleep(15)
                idle_for = time.time() - self._last_activity_at
                summary = {
                    "current_focus": "idle" if idle_for > 60 else "active_conversation",
                    "idle_seconds": int(idle_for),
                    "recent_cycle_count": len(self._recent_cycles),
                }
                await self.event_bus.publish(
                    "attention.summary.update",
                    {"summary": summary},
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Attention broadcast error: %s", exc)

    # === Health ===

    def health_pulse(self) -> HealthPulse:
        avg_cycle_ms = 0.0
        if self._recent_cycles:
            durations = [
                (c.completed_at - c.started_at) * 1000
                for c in self._recent_cycles[-20:]
                if c.completed_at
            ]
            avg_cycle_ms = sum(durations) / len(durations) if durations else 0
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "cycle_count": self._cycle_count,
                "daydream_count": self._daydream_count,
                "recent_cycle_count": len(self._recent_cycles),
                "avg_cycle_duration_ms": round(avg_cycle_ms, 2),
                "idle_seconds": round(time.time() - self._last_activity_at, 1),
                "saved_states_count": len(self._saved_states),
            },
        )
