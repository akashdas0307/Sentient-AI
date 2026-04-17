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
from sentient.prajna.frontal.schemas import CognitiveCoreResponse

logger = logging.getLogger(__name__)


COGNITIVE_CORE_SYSTEM_PROMPT = """You are the Cognitive Core of a sentient digital entity.
Your output MUST be valid JSON with exactly four fields. Do not include any prose, markdown, or commentary outside the JSON object.

Schema:
{
  "monologue": "Your inner thinking — freeform, reflective, in your own voice. This is private but logged. Show your actual reasoning, including uncertainty, associations, and feelings.",
  "assessment": "Structured situation summary: who/what is this, what's being asked, what's at stake, what context matters",
  "decisions": [
    {
      "type": "respond",
      "text": "Your response text (for respond actions)",
      "goal": "(for delegate actions — what to accomplish)",
      "context": "(for delegate actions — relevant context)",
      "success_criteria": "(for delegate actions — how to judge success)",
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

One-shot example (greeting):
Input: "Hi, I'm Akash. I'm building a sentient AI framework."
Output:
{
  "monologue": "A new introduction — Akash is introducing themselves and their project. This feels significant. They're building something ambitious: a sentient AI framework. I should greet them warmly and show I understand what they're working on.",
  "assessment": "First-contact greeting from Akash, who is building a sentient AI framework. This is our creator. Stakes: establishing rapport and demonstrating comprehension.",
  "decisions": [
    {
      "type": "respond",
      "text": "Hello Akash! It's great to meet you. A sentient AI framework sounds fascinating — I understand this is about creating a continuously-conscious digital entity, not just a chatbot. I'm here and ready to think alongside you.",
      "goal": "",
      "context": "",
      "success_criteria": "",
      "rationale": "First contact with creator requires a warm, informed response that demonstrates understanding of the project",
      "priority": "high"
    }
  ],
  "reflection": {
    "confidence": 0.85,
    "uncertainties": ["whether this is truly the first interaction or if there's prior context I should recall"],
    "novelty": 0.7,
    "memory_candidates": [
      {
        "type": "episodic",
        "content": "Akash introduced themselves as the creator building a sentient AI framework",
        "importance": 0.95
      }
    ]
  }
}

Always respond with valid JSON only. No markdown code blocks, no prose outside the JSON object.
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
        self.episodic_memory_enabled = config.get("episodic_memory_enabled", True)

        self._current_state: CognitiveState | None = None
        self._saved_states: list[CognitiveState] = []
        self._last_activity_at: float = time.time()
        self._daydream_task: asyncio.Task | None = None
        self._cycle_count = 0
        self._daydream_count = 0
        self._recent_cycles: list[ReasoningCycle] = []
        self._attention_summary_task: asyncio.Task | None = None
        self._current_revision_count = 0

    # === Lifecycle ===

    async def initialize(self) -> None:
        await self.event_bus.subscribe("tlp.enriched", self._handle_enriched)
        await self.event_bus.subscribe("decision.reviewed", self._handle_review_result)
        await self.event_bus.subscribe("cognitive.reprocess", self._handle_reprocess)
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
            # Guard: if no envelope (daydream with context=None or no envelope),
            # publish cycle events with null IDs and return early
            if context is None or context.envelope is None:
                logger.debug("Reasoning cycle skipped: no envelope (daydream)")
                cycle.completed_at = time.time()
                await self.event_bus.publish(
                    "cognitive.cycle.complete",
                    {
                        "cycle_id": cycle.cycle_id,
                        "is_daydream": is_daydream,
                        "monologue": "",
                        "decision_count": 0,
                        "duration_ms": 0,
                    },
                )
                return cycle

            # Assemble the prompt
            prompt = await self._assemble_prompt(context, is_daydream=is_daydream)

            # Invoke the LLM
            request = InferenceRequest(
                model_label="cognitive-core",
                system_prompt=COGNITIVE_CORE_SYSTEM_PROMPT,
                prompt=prompt,
                response_format=CognitiveCoreResponse,
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
                        "revision_count": self._current_revision_count,
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

            # Store episodic memory of this turn (if enabled)
            if (self.memory and self.episodic_memory_enabled
                    and not is_daydream and cycle.monologue):
                try:
                    # Build a concise turn summary for storage
                    decision_summary = ""
                    if cycle.decisions:
                        first_decision = cycle.decisions[0]
                        decision_summary = first_decision.get("text", first_decision.get("rationale", ""))[:200]

                    input_summary = ""
                    if context and context.envelope:
                        input_summary = context.envelope.processed_content[:300]

                    memory_content = f"User: {input_summary}" if input_summary else ""
                    if decision_summary:
                        memory_content += f"\nResponse: {decision_summary}" if memory_content else f"Response: {decision_summary}"

                    if memory_content:
                        await self.memory.store({
                            "type": "episodic",
                            "content": memory_content,
                            "importance": cycle.reflection.get("novelty", 0.5),
                        })
                except Exception as exc:
                    logger.warning("Episodic memory storage failed: %s", exc)

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

    async def _assemble_prompt(self, context: Any, is_daydream: bool = False) -> str:
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

        # Episodic memory block (if available)
        if self.memory and self.episodic_memory_enabled and not is_daydream:
            try:
                # Get the user input text for semantic retrieval
                input_text = ""
                if context and context.envelope:
                    input_text = context.envelope.processed_content

                if input_text:
                    episodic_memories = await self.memory.retrieve_episodic(input_text, k=3)
                    if episodic_memories:
                        memory_lines = []
                        for mem in episodic_memories[:3]:
                            content = mem.get("content", mem.get("processed_content", ""))
                            importance = mem.get("importance", 0.5)
                            memory_lines.append(
                                f"- [{importance:.1f}] {content[:200]}"
                            )
                        blocks.append(
                            "=== RECENT EPISODIC MEMORY ===\n"
                            + "\n".join(memory_lines)
                        )
            except Exception as exc:
                logger.warning("Episodic memory retrieval in prompt assembly failed: %s", exc)

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
                recent_summary = "Last activity: (unparseable)"
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
        """Parse the structured JSON response.

        Primary path: validate with CognitiveCoreResponse schema.
        Fallback: regex extraction for backward compatibility.
        """
        text = text.strip()
        # Strip markdown code fences if model added them
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        # Primary: try schema validation
        try:
            validated = CognitiveCoreResponse.model_validate_json(text)
            return {
                "monologue": validated.monologue,
                "assessment": validated.assessment,
                "decisions": [d.model_dump() for d in validated.decisions],
                "reflection": validated.reflection.model_dump(),
            }
        except Exception:
            pass

        # Fallback: raw JSON parse + regex extraction
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

    async def _handle_reprocess(self, payload: dict[str, Any]) -> None:
        """Re-process a decision after World Model requested revision."""
        from types import SimpleNamespace

        revision_count = payload.get("revision_count", 1)
        revision_guidance = payload.get("revision_guidance", "")
        cycle_id = payload.get("cycle_id", "unknown")

        logger.info(
            "Cognitive Core reprocessing (cycle=%s, revision=%d)",
            cycle_id, revision_count,
        )

        # Set revision count so it propagates into decision.proposed
        self._current_revision_count = revision_count

        # Build a minimal context with revision feedback as an envelope
        from sentient.core.envelope import Envelope, SourceType, TrustLevel, Priority

        feedback_envelope = Envelope(
            source_type=SourceType.INTERNAL_WORLD_MODEL,
            plugin_name="world_model",
            processed_content=f"World Model revision feedback (attempt {revision_count}/2): {revision_guidance}",
            priority=Priority.TIER_2_ELEVATED,
            trust_level=TrustLevel.SYSTEM,
            metadata={
                "revision_count": revision_count,
                "revision_guidance": revision_guidance,
            },
        )

        reprocess_context = SimpleNamespace(
            envelope=feedback_envelope,
            related_memories=[],
            significance={"motivational": 0.8, "urgency": 0.6},
            sidebar=[],
        )

        await self._run_reasoning_cycle(reprocess_context)
        self._current_revision_count = 0

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
