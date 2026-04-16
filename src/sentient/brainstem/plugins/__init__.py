"""Brainstem output plugins."""

from sentient.brainstem.plugins.base import OutputPlugin, OutputCommand, OutputResult
from sentient.brainstem.plugins.chat_output import ChatOutputPlugin

__all__ = ["OutputPlugin", "OutputCommand", "OutputResult", "ChatOutputPlugin"]
