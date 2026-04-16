"""Chat Output Plugin — send messages to System GUI chat via WebSocket.

Mirror of ChatInputPlugin. The API layer holds the WebSocket connections;
this plugin pushes outgoing messages to a shared queue that the API drains.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sentient.brainstem.plugins.base import OutputCommand, OutputPlugin, OutputResult
from sentient.core.module_interface import ModuleStatus

logger = logging.getLogger(__name__)


class ChatOutputPlugin(OutputPlugin):
    """Delivers messages to the System GUI chat."""

    PLUGIN_CATEGORY = "communication"
    CAPABILITIES = ["text_chat", "creator_communication"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("chat_output", config)
        # Outgoing message queue — drained by API WebSocket handlers
        self.outgoing_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def initialize(self) -> None:
        logger.info("ChatOutputPlugin initialized")

    async def start(self) -> None:
        self.set_status(ModuleStatus.HEALTHY)

    async def shutdown(self) -> None:
        pass

    async def execute(self, command: OutputCommand) -> OutputResult:
        """Queue a chat message for WebSocket delivery."""
        start = time.time()
        self._command_count += 1

        try:
            text = command.parameters.get("text", "")
            if not text:
                return OutputResult(
                    command_id=command.command_id,
                    success=False,
                    error="No text in command",
                    duration_ms=(time.time() - start) * 1000,
                )

            message = {
                "type": "chat_message",
                "sender": "sentient",
                "text": text,
                "timestamp": time.time(),
                "metadata": command.parameters.get("metadata", {}),
            }

            await self.outgoing_queue.put(message)
            self._success_count += 1

            return OutputResult(
                command_id=command.command_id,
                success=True,
                output={"queued": True},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            self._failure_count += 1
            return OutputResult(
                command_id=command.command_id,
                success=False,
                error=str(exc),
                duration_ms=(time.time() - start) * 1000,
            )
