"""Wetware test fixtures — requires running Ollama with GLM-4.6 and MiniMax-M2 models."""
from __future__ import annotations

import pytest

from sentient.core.inference_gateway import InferenceGateway


@pytest.fixture
def real_gateway() -> InferenceGateway:
    """Real InferenceGateway connecting to local Ollama."""
    return InferenceGateway({"base_url": "http://localhost:11434"})
