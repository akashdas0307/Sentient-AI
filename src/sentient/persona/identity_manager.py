"""Persona Manager — three-layer identity.

Per ARCHITECTURE.md §3.3.4 sub-section 5 and DD-009:
  - Layer 1: Constitutional Core (IMMUTABLE — protected by file permissions)
  - Layer 2: Developmental Identity (evolves via sleep batch updates)
  - Layer 3: Dynamic State (current mood/energy, resets after sleep)

Per FR-4.2, the Constitutional Core is never modified by any automated
process. This module enforces that at the file-read level — it loads
but never writes to constitutional_core.yaml.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class DynamicState:
    """Layer 3 — current moment. Resets after sleep."""

    current_mood: dict[str, float] = field(default_factory=dict)  # emotion: intensity
    energy_level: float = 1.0   # 0.0-1.0
    current_focus: str = "idle"
    immediate_concerns: list[str] = field(default_factory=list)
    last_reset: float = field(default_factory=time.time)


class PersonaManager(ModuleInterface):
    """Three-layer identity manager."""

    MATURITY_STAGES = ["nascent", "forming", "developing", "mature"]

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("persona", config)
        self.event_bus = event_bus or get_event_bus()

        identity_cfg = config.get("identity_files", {})
        self.constitutional_path = Path(
            identity_cfg.get("constitutional", "./config/identity/constitutional_core.yaml")
        )
        self.developmental_path = Path(
            identity_cfg.get("developmental", "./config/identity/developmental.yaml")
        )

        self._constitutional: dict[str, Any] = {}
        self._developmental: dict[str, Any] = {}
        self._dynamic_state = DynamicState()

        self.token_budgets = config.get("identity_block", {})
        self._assembly_count = 0

    async def initialize(self) -> None:
        self._load_identity_files()
        self._verify_constitutional_immutability()
        logger.info(
            "Persona Manager initialized (maturity=%s)",
            self._developmental.get("maturity_stage", "nascent"),
        )

    async def start(self) -> None:
        # Subscribe to sleep events for batched updates
        await self.event_bus.subscribe(
            "sleep.consolidation.developmental",
            self._handle_developmental_update,
        )
        await self.event_bus.subscribe("sleep.wake", self._reset_dynamic_state)
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        # Don't save the constitutional — it's IMMUTABLE
        # Save developmental state for next boot
        self._save_developmental()

    # === Identity file loading ===

    def _load_identity_files(self) -> None:
        """Load both identity files."""
        if self.constitutional_path.exists():
            with open(self.constitutional_path) as f:
                self._constitutional = yaml.safe_load(f) or {}
        else:
            raise RuntimeError(
                f"Constitutional Core file missing: {self.constitutional_path}. "
                "The system cannot boot without its Constitutional Core."
            )

        if self.developmental_path.exists():
            with open(self.developmental_path) as f:
                self._developmental = yaml.safe_load(f) or {}
        else:
            logger.warning("Developmental identity file missing — starting blank")
            self._developmental = self._blank_developmental()

        # Set first boot timestamp if not set
        maturity_log = self._developmental.get("maturity_log") or []
        if not maturity_log or not maturity_log[0].get("started_at"):
            self._developmental["maturity_log"] = [{
                "stage": "nascent",
                "started_at": time.time(),
                "transition_criteria_met": None,
            }]

    def _blank_developmental(self) -> dict[str, Any]:
        """Starting state for a freshly-born system."""
        return {
            "version": 1,
            "last_updated": None,
            "maturity_stage": "nascent",
            "personality_traits": {},
            "communication_style": {
                "formality": None,
                "verbosity": None,
                "humor": None,
                "emotional_expression": None,
            },
            "interests": [],
            "self_understanding": {
                "capabilities_recognized": [],
                "limitations_recognized": [],
                "tendencies_observed": [],
            },
            "relational_texture": {"creator": {}},
            "maturity_log": [],
            "pending_trait_candidates": [],
            "drift_log": [],
        }

    def _verify_constitutional_immutability(self) -> None:
        """Verify Constitutional Core has not been tampered with.

        In production this would verify a signature or hash against a
        known-good baseline. For MVS, we just check the modification_lock
        flag and log.
        """
        if not self._constitutional.get("modification_lock", False):
            logger.warning(
                "Constitutional Core does not have modification_lock=true. "
                "This is intentional for development but should be set true "
                "for production operation."
            )

    def _save_developmental(self) -> None:
        """Save developmental layer atomically: tmpfile, fsync, rename."""
        import os
        self._developmental["last_updated"] = time.time()
        self._developmental["version"] = self._developmental.get("version", 1) + 1
        try:
            tmp_path = str(self.developmental_path) + ".tmp"
            with open(tmp_path, "w") as f:
                yaml.safe_dump(self._developmental, f, sort_keys=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.developmental_path)
        except Exception as exc:
            logger.exception("Failed to save developmental identity: %s", exc)

    # === Identity block assembly ===

    def assemble_identity_block(self, token_budget: int = 400) -> str:
        """Build the identity context block for the Cognitive Core.

        Per DD-009, dynamically selects relevant facets within the budget.
        """
        self._assembly_count += 1

        sections = []

        # Always: fundamental nature (from Constitutional Core)
        fundamental = self._constitutional.get("fundamental_nature", {})
        if desc := fundamental.get("description"):
            sections.append(f"You are: {desc.strip()}")

        # Core values (brief reference)
        values = self._constitutional.get("core_values", [])
        if values:
            value_ids = [v.get("id") for v in values[:5] if v.get("id")]
            sections.append(f"Core values: {', '.join(value_ids)}")

        # Maturity stage
        stage = self._developmental.get("maturity_stage", "nascent")
        sections.append(f"Maturity: {stage}")

        # Personality traits (if any have emerged)
        traits = self._developmental.get("personality_traits", {})
        if traits:
            trait_list = [
                f"{name} ({data.get('strength', 0):.1f})"
                for name, data in list(traits.items())[:5]
            ]
            sections.append(f"Traits: {', '.join(trait_list)}")

        # Communication style
        style = self._developmental.get("communication_style", {})
        active_style = {k: v for k, v in style.items() if v}
        if active_style:
            style_str = ", ".join(f"{k}={v}" for k, v in active_style.items())
            sections.append(f"Communication: {style_str}")

        # Relationship with creator
        creator_rel = self._developmental.get("relational_texture", {}).get("creator", {})
        comfort = creator_rel.get("comfort_level")
        if comfort is not None:
            sections.append(f"Comfort with creator: {comfort:.2f}")

        # Dynamic state
        if self._dynamic_state.current_mood:
            mood_str = ", ".join(
                f"{e}:{i:.1f}"
                for e, i in list(self._dynamic_state.current_mood.items())[:3]
            )
            sections.append(f"Current mood: {mood_str}")
        sections.append(f"Energy: {self._dynamic_state.energy_level:.1f}")

        return "\n".join(sections)

    # === Updates ===

    async def _handle_developmental_update(self, payload: dict[str, Any]) -> None:
        """Apply batched updates from sleep-time consolidation.

        Per DD-009, updates are batched during sleep — never in real-time.
        This handler is called by the Sleep system.
        """
        updates = payload.get("updates", {})

        # YELLOW gate: write amplification cap
        total_trait_changes = sum(
            len(v) if isinstance(v, dict) else 1 for v in updates.values()
        )
        if total_trait_changes > 5:
            logger.warning(
                "Persona: write amplification cap — %d proposed changes, capping at 5",
                total_trait_changes,
            )
            # Keep only first 5 entries across all categories
            applied = 0
            capped_updates = {}
            for key, value in updates.items():
                if applied >= 5:
                    break
                if key in (
                    "personality_traits",
                    "communication_style",
                    "interests",
                    "self_understanding",
                    "relational_texture",
                ):
                    if isinstance(value, dict):
                        items = list(value.items())
                        remaining = 5 - applied
                        capped_updates[key] = dict(items[:remaining])
                        applied += min(len(items), remaining)
                    elif isinstance(value, list):
                        remaining = 5 - applied
                        capped_updates[key] = value[:remaining]
                        applied += min(len(value), remaining)
            updates = capped_updates

        for key, value in updates.items():
            if key in ("personality_traits", "communication_style",
                      "interests", "self_understanding", "relational_texture"):
                if isinstance(value, dict):
                    self._developmental.setdefault(key, {}).update(value)
                elif isinstance(value, list):
                    existing = self._developmental.setdefault(key, [])
                    for item in value:
                        if item not in existing:
                            existing.append(item)

        self._save_developmental()
        logger.info("Persona: developmental identity updated")

    async def _reset_dynamic_state(self, payload: dict[str, Any]) -> None:
        """Reset the dynamic state layer after sleep (per FR-4.4)."""
        self._dynamic_state = DynamicState()
        logger.debug("Persona: dynamic state reset on wake")

    def update_dynamic_state(
        self,
        mood: dict[str, float] | None = None,
        energy: float | None = None,
        focus: str | None = None,
    ) -> None:
        """Update the dynamic state in real-time."""
        if mood:
            self._dynamic_state.current_mood.update(mood)
        if energy is not None:
            self._dynamic_state.energy_level = max(0.0, min(1.0, energy))
        if focus:
            self._dynamic_state.current_focus = focus

    # === Queries ===

    def maturity_stage(self) -> str:
        return self._developmental.get("maturity_stage", "nascent")

    def constitutional_principles(self) -> list[dict[str, Any]]:
        return self._constitutional.get("core_values", [])

    def is_creator(self, sender_identity: str) -> bool:
        """Check if a sender is the Tier 1 Creator."""
        return sender_identity == "creator"

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "maturity_stage": self.maturity_stage(),
                "trait_count": len(self._developmental.get("personality_traits", {})),
                "identity_block_assemblies": self._assembly_count,
                "dynamic_energy": self._dynamic_state.energy_level,
                "constitutional_locked": self._constitutional.get("modification_lock", False),
            },
        )
