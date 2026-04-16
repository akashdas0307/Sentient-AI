"""Base class for all Thalamus input plugins.

Per ARCHITECTURE.md §3.1, every input plugin implements this contract:
  - Registration (capabilities, data formats, resource needs)
  - Output in standard envelope format
  - Health heartbeat
  - Control channel (pause, resume, adjust, shutdown)

Plugins do their own domain-specific preprocessing before producing
envelopes — like how the retina preprocesses photons before sending
signals to the thalamus.
"""
from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from typing import Any

from sentient.core.envelope import Envelope
from sentient.core.module_interface import HealthPulse, ModuleInterface


# Callback signature: plugin invokes this when it has an envelope to deliver
EnvelopeCallback = Callable[[Envelope], Awaitable[None]]


class InputPlugin(ModuleInterface):
    """Base class for all input plugins.

    Subclasses implement the actual input source logic (chat, audio,
    visual, etc.) and call `await self.emit(envelope)` to forward
    envelopes to the Thalamus.
    """

    # Plugin permission tier (per ARCHITECTURE.md §3.1)
    PERMISSION_TIER = "approved"   # 'core' | 'approved' | 'self_created'

    # Capabilities this plugin offers (declared at registration)
    CAPABILITIES: list[str] = []

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        emit_callback: EnvelopeCallback | None = None,
    ) -> None:
        super().__init__(name, config)
        self._emit_callback = emit_callback
        self._envelope_count = 0

    def set_emit_callback(self, callback: EnvelopeCallback) -> None:
        """Set the callback used to deliver envelopes to the Thalamus."""
        self._emit_callback = callback

    async def emit(self, envelope: Envelope) -> None:
        """Deliver an envelope to the Thalamus.

        Called by the plugin's input handler whenever new data arrives.
        """
        if self._emit_callback is None:
            raise RuntimeError(
                f"Plugin {self.name} has no emit callback set. "
                "Plugin must be registered with the Thalamus before emitting."
            )
        envelope.plugin_name = self.name
        self._envelope_count += 1
        await self._emit_callback(envelope)

    def envelope_count(self) -> int:
        """Total envelopes emitted (for health metrics)."""
        return self._envelope_count

    def health_pulse(self) -> HealthPulse:
        """Default health pulse — subclasses can extend."""
        pulse = super().health_pulse()
        pulse.metrics["envelopes_emitted"] = self._envelope_count
        pulse.metrics["permission_tier"] = self.PERMISSION_TIER
        pulse.metrics["capabilities"] = self.CAPABILITIES
        return pulse

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Setup the input source (open connections, load models, etc.)."""
        ...

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin accepting inputs."""
        ...

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Close input source cleanly."""
        ...
