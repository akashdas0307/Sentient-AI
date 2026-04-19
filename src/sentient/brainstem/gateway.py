"""Brainstem Gateway — Output Gateway.

Per ARCHITECTURE.md §3.4 and DD-022:
  - Receives approved decisions from World Model
  - Action Translator maps decisions to plugin commands
  - Output Coordinator for multi-output actions
  - Feedback Manager for retries
  - Safety Gate for irreversible actions
  - Reflex System for pure deterministic responses
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sentient.brainstem.plugins.base import OutputCommand, OutputPlugin, OutputResult
from sentient.core.event_bus import EventBus, get_event_bus
from sentient.core.module_interface import HealthPulse, ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class Brainstem(ModuleInterface):
    """Output Gateway — routes Cognitive Core decisions to output plugins."""

    def __init__(
        self,
        config: dict[str, Any],
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__("brainstem", config)
        self.event_bus = event_bus or get_event_bus()

        safety_cfg = config.get("safety_gate", {})
        self.irreversible_delay = safety_cfg.get("irreversible_action_delay_seconds", 2)
        self.rate_limit_per_minute = safety_cfg.get("rate_limit_per_minute", 30)

        retry_cfg = config.get("retry", {})
        self.max_retries = retry_cfg.get("max_attempts", 3)
        self.retry_backoff = retry_cfg.get("backoff_seconds", [1, 3, 8])

        self._plugins: dict[str, OutputPlugin] = {}
        self._capability_map: dict[str, str] = {}   # capability → plugin name

        self._rate_limit_window: list[float] = []
        self._executed_count = 0
        self._failed_count = 0

    # === Lifecycle ===

    async def initialize(self) -> None:
        await self.event_bus.subscribe("brainstem.output_approved", self._handle_approved)

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        for plugin in self._plugins.values():
            try:
                await plugin.shutdown()
            except Exception:
                pass

    # === Plugin management ===

    async def register_plugin(self, plugin: OutputPlugin) -> None:
        """Register an output plugin."""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin {plugin.name} already registered")
        await plugin.initialize()
        await plugin.start()
        self._plugins[plugin.name] = plugin
        for capability in plugin.CAPABILITIES:
            self._capability_map[capability] = plugin.name
        logger.info(
            "Brainstem registered plugin: %s (capabilities=%s)",
            plugin.name, plugin.CAPABILITIES,
        )

    def get_plugin(self, name: str) -> OutputPlugin | None:
        return self._plugins.get(name)

    # === Decision handling ===

    async def _handle_approved(self, payload: dict[str, Any]) -> None:
        """Receive an approved decision from the Decision Arbiter."""
        decision = payload["decision"]
        advisory = payload.get("advisory_notes", "")
        turn_id = payload.get("turn_id", "unknown")
        escalated = payload.get("escalated", False)
        escalation_reason = payload.get("escalation_reason", "")

        if escalated:
            logger.info(
                "Brainstem executing ESCALATED decision (turn=%s, reason=%s): type=%s",
                turn_id, escalation_reason, decision.get("type"),
            )

        try:
            await self._execute_decision(decision, advisory)
        except Exception as exc:
            logger.exception("Brainstem execution error: %s", exc)
            self._failed_count += 1
            self.set_status(ModuleStatus.ERROR, str(exc))

    async def _execute_decision(
        self,
        decision: dict[str, Any],
        advisory: str,
    ) -> None:
        """Translate decision to plugin command and execute."""
        decision_type = decision.get("type", "")
        parameters = decision.get("parameters", {})
        logger.info("Brainstem executing decision type=%s parameters=%s advisory=%r", decision_type, parameters, advisory)

        # Map decision type to plugin capability
        if decision_type == "respond":
            # Per D1: DecisionAction schema enforces explicit `text` field.
            # The schema-validated format has `text` at the top level.
            # The legacy fallback format has `text` nested in `parameters`.
            # Support both during the transition period.
            text = decision.get("text", "")
            if not text.strip():
                # Try legacy parameters nesting
                text = parameters.get("text", "")
            if not text.strip():
                # Fallback: try known variant keys (one release cycle, then remove)
                text = (
                    parameters.get("content")
                    or parameters.get("message")
                    or ""
                )
                if text.strip():
                    logger.warning(
                        "Brainstem: response text in non-canonical key — "
                        "schema enforcement should prevent this"
                    )
            if not text.strip():
                # Last resort: longest string heuristic (one release cycle, then remove)
                string_vals = [v for v in parameters.values() if isinstance(v, str) and len(v) > 10]
                if string_vals:
                    text = max(string_vals, key=len)
                    logger.warning(
                        "Brainstem: falling back to longest-string heuristic — "
                        "schema enforcement should prevent this"
                    )
            if not text.strip():
                logger.warning("Brainstem: no response text, falling back to advisory")
                text = advisory
            capability = "text_chat"
            plugin_params = {
                "text": text or "(no response content)",
                "metadata": {"advisory": advisory} if advisory else {},
            }
        elif decision_type == "delegate":
            # Delegation goes through the Harness Adapter, not output plugin
            await self.event_bus.publish(
                "harness.delegate",
                {
                    "goal": parameters.get("goal", ""),
                    "context": parameters.get("context", {}),
                    "constraints": parameters.get("constraints", {}),
                    "success_criteria": parameters.get("success_criteria", []),
                },
            )
            return
        elif decision_type in ("wait", "reflect", "query_memory"):
            # These are internal — no external output
            return
        else:
            logger.warning("Unknown decision type: %s", decision_type)
            return

        # Rate limit check
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded — deferring output")
            return

        # Safety gate: add delay for irreversible actions
        if self._is_irreversible(decision):
            await asyncio.sleep(self.irreversible_delay)

        # Route to plugin
        plugin_name = self._capability_map.get(capability)
        logger.info("Brainstem plugin lookup: capability=%r map=%s plugin_name=%r", capability, self._capability_map, plugin_name)
        if not plugin_name:
            logger.error("No plugin supports capability: %s", capability)
            self._failed_count += 1
            return

        plugin = self._plugins[plugin_name]
        command = OutputCommand(
            capability=capability,
            parameters=plugin_params,
        )

        result = await self._execute_with_retry(plugin, command)
        if result.success:
            self._executed_count += 1
            await self.event_bus.publish(
                "action.executed",
                {
                    "command_id": command.command_id,
                    "plugin": plugin_name,
                    "capability": capability,
                    "duration_ms": result.duration_ms,
                },
            )
        else:
            self._failed_count += 1
            await self.event_bus.publish(
                "action.failed",
                {
                    "command_id": command.command_id,
                    "plugin": plugin_name,
                    "error": result.error,
                },
            )

    async def _execute_with_retry(
        self,
        plugin: OutputPlugin,
        command: OutputCommand,
    ) -> OutputResult:
        """Execute with retries on failure."""
        last_result: OutputResult | None = None
        for attempt in range(self.max_retries):
            result = await plugin.execute(command)
            if result.success:
                return result
            last_result = result
            if attempt < self.max_retries - 1:
                backoff = self.retry_backoff[
                    min(attempt, len(self.retry_backoff) - 1)
                ]
                await asyncio.sleep(backoff)
        return last_result or OutputResult(
            command_id=command.command_id, success=False, error="unknown"
        )

    def _check_rate_limit(self) -> bool:
        """Simple sliding-window rate limiter."""
        now = time.time()
        cutoff = now - 60
        self._rate_limit_window = [t for t in self._rate_limit_window if t > cutoff]
        if len(self._rate_limit_window) >= self.rate_limit_per_minute:
            return False
        self._rate_limit_window.append(now)
        return True

    def _is_irreversible(self, decision: dict) -> bool:
        """Check if a decision is an irreversible action.

        MVS: chat responses are reversible (user can ignore). File deletions,
        email sends, and physical world actions would be irreversible.
        """
        irreversible_types = {"delete", "send_email", "physical_action"}
        return decision.get("type") in irreversible_types

    def health_pulse(self) -> HealthPulse:
        return HealthPulse(
            module_name=self.name,
            status=self._last_health_status,
            metrics={
                "executed_count": self._executed_count,
                "failed_count": self._failed_count,
                "active_plugins": list(self._plugins.keys()),
                "capabilities": list(self._capability_map.keys()),
                "rate_limit_usage": len(self._rate_limit_window),
            },
        )
