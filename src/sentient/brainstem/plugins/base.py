"""Base class for Brainstem output plugins.

Mirror of Thalamus input plugins. Each output plugin implements a
specific output channel (chat, voice, email, etc.) and exposes
capabilities to the Brainstem's routing layer.
"""
from __future__ import annotations

import abc
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sentient.core.module_interface import HealthPulse, ModuleInterface


@dataclass
class OutputCommand:
    """A command the Brainstem sends to an output plugin."""

    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capability: str = ""       # Which capability is being invoked
    parameters: dict[str, Any] = field(default_factory=dict)
    target: str | None = None  # Destination (e.g., chat session id)
    created_at: float = field(default_factory=time.time)


@dataclass
class OutputResult:
    """Result returned by an output plugin."""

    command_id: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class OutputPlugin(ModuleInterface):
    """Base class for output channels (chat, voice, email, etc.)."""

    PLUGIN_CATEGORY = "communication"   # 'communication' | 'direct_action' | 'shared_capability' | 'physical'
    CAPABILITIES: list[str] = []

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._command_count = 0
        self._success_count = 0
        self._failure_count = 0

    @abc.abstractmethod
    async def execute(self, command: OutputCommand) -> OutputResult:
        """Execute an output command. Must return a result."""
        ...

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def health_pulse(self) -> HealthPulse:
        pulse = super().health_pulse()
        pulse.metrics.update({
            "category": self.PLUGIN_CATEGORY,
            "capabilities": self.CAPABILITIES,
            "command_count": self._command_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
        })
        return pulse
