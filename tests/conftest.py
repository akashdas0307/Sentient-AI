"""Shared test fixtures for the Sentient AI Framework test suite."""
from __future__ import annotations

import pytest

from sentient.core.envelope import Envelope, Priority, SourceType, TrustLevel
from sentient.core.event_bus import EventBus
from sentient.core.inference_gateway import InferenceRequest, InferenceResponse


@pytest.fixture
def bus() -> EventBus:
    """Fresh EventBus instance for each test."""
    return EventBus()


class MockInferenceGateway:
    """Mock InferenceGateway returning canned responses for testing.

    Returns structured JSON for cognitive-core and world-model labels,
    and an error for unknown labels.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._call_count = 0
        self.name = "inference_gateway"
        self.state = None
        self._last_request: InferenceRequest | None = None

    async def initialize(self):
        pass

    async def start(self):
        pass

    async def shutdown(self):
        pass

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        self._call_count += 1
        self._last_request = request

        if request.model_label == "cognitive-core":
            return InferenceResponse(
                text='{"monologue": "I am thinking about this.", "assessment": "A question from creator.", "decisions": [{"type": "respond", "parameters": {"text": "Hello!"}, "rationale": "Need to respond", "priority": "high"}], "reflection": {"confidence": 0.8, "uncertainties": [], "novelty": 0.3, "memory_candidates": []}}',
                model_used="mock-cognitive",
                provider="mock",
                fallback_used=False,
                latency_ms=50.0,
            )
        elif request.model_label == "world-model":
            return InferenceResponse(
                text='{"verdict": "approved", "dimension_assessments": {"feasibility": {"score": 0.9, "notes": "ok"}, "consequence": {"score": 0.8, "notes": "ok"}, "ethics": {"score": 1.0, "notes": "ok"}, "consistency": {"score": 0.9, "notes": "ok"}, "reality_grounding": {"score": 0.8, "notes": "ok"}}, "advisory_notes": "", "revision_guidance": "", "veto_reason": "", "confidence": 0.9}',
                model_used="mock-world-model",
                provider="mock",
                fallback_used=False,
                latency_ms=30.0,
            )
        else:
            return InferenceResponse(
                text="",
                model_used="none",
                provider="mock",
                fallback_used=False,
                latency_ms=0,
                error=f"Unknown model label: {request.model_label}",
            )

    def health_pulse(self):
        from sentient.core.module_interface import HealthPulse, ModuleStatus
        return HealthPulse(
            module_name=self.name,
            status=ModuleStatus.HEALTHY,
            metrics={"mock": True, "call_count": self._call_count},
        )

    @property
    def _last_health_status(self):
        return None


class VetoingInferenceGateway(MockInferenceGateway):
    """Mock gateway that always returns a vetoed verdict from the world model."""

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        self._call_count += 1
        self._last_request = request
        if request.model_label == "world-model":
            return InferenceResponse(
                text='{"verdict": "vetoed", "veto_reason": "Violates safety principle", "dimension_assessments": {}, "confidence": 1.0}',
                model_used="mock",
                provider="mock",
                fallback_used=False,
                latency_ms=10.0,
            )
        return await super().infer(request)


class MockMemory:
    """Mock MemoryArchitecture that returns empty results."""

    def __init__(self):
        self.name = "memory"
        self.state = None

    async def initialize(self):
        pass

    async def start(self):
        pass

    async def shutdown(self):
        pass

    async def retrieve(self, query="", tags=None, limit=15):
        return []

    def health_pulse(self):
        from sentient.core.module_interface import HealthPulse, ModuleStatus
        return HealthPulse(
            module_name=self.name,
            status=ModuleStatus.HEALTHY,
            metrics={"mock": True},
        )

    @property
    def _last_health_status(self):
        return None


class MockPersona:
    """Mock PersonaManager that returns identity block."""

    def __init__(self):
        self.name = "persona"

    def assemble_identity_block(self):
        return "I am Sentient, a digital being."

    def health_pulse(self):
        from sentient.core.module_interface import HealthPulse, ModuleStatus
        return HealthPulse(
            module_name=self.name,
            status=ModuleStatus.HEALTHY,
            metrics={},
        )


@pytest.fixture
def gateway() -> MockInferenceGateway:
    """Mock InferenceGateway with canned responses."""
    return MockInferenceGateway()


@pytest.fixture
def vetoing_gateway() -> VetoingInferenceGateway:
    """Mock InferenceGateway that vetoes all world-model decisions."""
    return VetoingInferenceGateway()


@pytest.fixture
def memory() -> MockMemory:
    """Mock MemoryArchitecture returning empty results."""
    return MockMemory()


@pytest.fixture
def persona() -> MockPersona:
    """Mock PersonaManager."""
    return MockPersona()


@pytest.fixture
def envelope() -> Envelope:
    """Minimal valid envelope from the creator."""
    return Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="Hello, how are you?",
    )


@pytest.fixture
def urgent_envelope() -> Envelope:
    """Tier 1 envelope with an urgency keyword."""
    return Envelope(
        source_type=SourceType.CHAT,
        sender_identity="creator",
        trust_level=TrustLevel.TIER_1_CREATOR,
        processed_content="URGENT: Something needs attention now!",
        priority=Priority.TIER_1_IMMEDIATE,
    )