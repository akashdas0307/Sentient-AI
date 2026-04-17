"""Wetware test fixtures — requires running Ollama with GLM-5.1 and MiniMax-M2 models."""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from sentient.core.inference_gateway import InferenceGateway


@pytest.fixture
def real_gateway() -> InferenceGateway:
    """Real InferenceGateway connecting to local Ollama with config from inference_gateway.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config" / "inference_gateway.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return InferenceGateway(config)
