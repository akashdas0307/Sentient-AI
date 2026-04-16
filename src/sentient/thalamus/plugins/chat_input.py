"""Chat Input Plugin — System GUI text chat.

This is the ONLY input plugin in MVS scope. The creator types messages
in the System GUI; this plugin receives them via WebSocket and forwards
as envelopes to the Thalamus.

Per the multi-human handling design (FR-9), in MVS all chat is from
the Tier 1 Creator.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sentient.core.envelope import Envelope, Priority, SourceType, TrustLevel
from sentient.core.module_interface import ModuleStatus
from sentient.thalamus.plugins.base import InputPlugin

logger = logging.getLogger(__name__)


class ChatInputPlugin(InputPlugin):
    """Receives chat messages from the System GUI WebSocket.

    The actual WebSocket endpoint lives in the API layer (sentient.api).
    The API forwards messages to this plugin via the inject() method.
    """

    PERMISSION_TIER = "core"
    CAPABILITIES = ["text_chat", "creator_communication"]

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        emit_callback=None,
    ) -> None:
        super().__init__("chat_input", config, emit_callback)
        self._inbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """No external resources to initialize for chat input."""
        logger.info("ChatInputPlugin initialized")

    async def start(self) -> None:
        """Begin processing inbound chat messages."""
        self._processor_task = asyncio.create_task(self._process_loop())
        self.set_status(ModuleStatus.HEALTHY)
        logger.info("ChatInputPlugin started")

    async def shutdown(self) -> None:
        """Stop the processor task."""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def inject(self, message: dict[str, Any]) -> None:
        """Public entry point: API layer calls this when a message arrives.

        Expected message shape:
          {
            "text": "<message content>",
            "timestamp": <unix seconds>,   # optional
            "session_id": "<session>",     # optional
          }
        """
        await self._inbound_queue.put(message)

    async def _process_loop(self) -> None:
        """Consume from inbound queue and emit envelopes."""
        while True:
            try:
                message = await self._inbound_queue.get()
                envelope = self._message_to_envelope(message)
                await self.emit(envelope)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Chat input processing error: %s", exc)
                self.set_status(ModuleStatus.ERROR, str(exc))

    def _message_to_envelope(self, message: dict[str, Any]) -> Envelope:
        """Convert raw chat message into a standard envelope."""
        text = message.get("text", "").strip()

        envelope = Envelope(
            source_type=SourceType.CHAT,
            sender_identity="creator",          # MVS: only one user
            trust_level=TrustLevel.TIER_1_CREATOR,
            raw_content=message,
            processed_content=text,
            metadata={
                "session_id": message.get("session_id"),
                "channel": "system_gui",
            },
        )

        # Light intent detection (will be refined by Checkpost)
        if text.endswith("?"):
            envelope.add_tag("intent", "question")
        elif text.startswith(("/", "!")):
            envelope.add_tag("intent", "command")
        else:
            envelope.add_tag("intent", "statement")

        # Greeting detection
        greetings = {"hi", "hello", "hey", "good morning", "good evening"}
        if text.lower().strip(".!?") in greetings:
            envelope.add_tag("intent", "greeting")

        # Default priority: Tier 2 (creator messages always at least elevated)
        envelope.priority = Priority.TIER_2_ELEVATED

        return envelope
