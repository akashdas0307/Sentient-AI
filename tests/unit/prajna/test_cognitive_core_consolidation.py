"""Tests for semantic and procedural memory injection in Cognitive Core (D5)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.core.event_bus import EventBus, reset_event_bus


@pytest.fixture
def event_bus():
    reset_event_bus()
    bus = EventBus()
    return bus


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.infer = AsyncMock()
    gw.shutdown = AsyncMock()
    return gw


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.retrieve_episodic = AsyncMock(return_value=[])
    mem.retrieve_semantic = AsyncMock(return_value=[])
    mem.retrieve_procedural = AsyncMock(return_value=[])
    mem.store = AsyncMock(return_value="test-memory-id")
    return mem


@pytest.fixture
def cognitive_core(event_bus, mock_gateway, mock_memory):
    cc = CognitiveCore(
        config={
            "episodic_memory_enabled": True,
            "semantic_enabled": True,
            "procedural_enabled": True,
        },
        inference_gateway=mock_gateway,
        memory=mock_memory,
        event_bus=event_bus,
    )
    return cc


class TestConsolidatedKnowledgeInjection:
    """Test that semantic facts are injected into the prompt."""

    @pytest.mark.asyncio
    async def test_semantic_facts_in_prompt(self, cognitive_core, mock_memory):
        """When semantic facts exist, they appear under CONSOLIDATED KNOWLEDGE."""
        mock_memory.retrieve_semantic.return_value = [
            {"statement": "Akash prefers Python", "confidence": 0.85},
            {"statement": "The system should be honest", "confidence": 0.9},
        ]

        envelope = MagicMock()
        envelope.processed_content = "What does Akash prefer?"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" in prompt
        assert "Akash prefers Python" in prompt
        assert "The system should be honest" in prompt
        assert "[0.9]" in prompt or "[0.8]" in prompt

    @pytest.mark.asyncio
    async def test_semantic_facts_omitted_when_empty(self, cognitive_core, mock_memory):
        """When no semantic facts exist, the section is OMITTED entirely."""
        mock_memory.retrieve_semantic.return_value = []

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt
        assert "No facts" not in prompt

    @pytest.mark.asyncio
    async def test_semantic_facts_omitted_when_disabled(self, mock_memory):
        """When semantic_enabled=False, section is omitted even if facts exist."""
        event_bus = EventBus()
        mock_gateway = MagicMock()
        mock_gateway.infer = AsyncMock()
        mock_gateway.shutdown = AsyncMock()

        cc = CognitiveCore(
            config={
                "episodic_memory_enabled": True,
                "semantic_enabled": False,
                "procedural_enabled": True,
            },
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        mock_memory.retrieve_semantic.return_value = [
            {"statement": "Akash prefers Python", "confidence": 0.85},
        ]

        envelope = MagicMock()
        envelope.processed_content = "What does Akash prefer?"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cc._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt

    @pytest.mark.asyncio
    async def test_semantic_facts_skipped_in_daydream(self, cognitive_core, mock_memory):
        """During daydreaming, semantic facts are NOT retrieved."""
        mock_memory.retrieve_semantic.return_value = [
            {"statement": "Akash prefers Python", "confidence": 0.85},
        ]

        # Daydream — no context/envelope
        prompt = await cognitive_core._assemble_prompt(context=None, is_daydream=True)

        mock_memory.retrieve_semantic.assert_not_called()
        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt

    @pytest.mark.asyncio
    async def test_semantic_retrieval_called_with_input_text(
        self, cognitive_core, mock_memory, mock_gateway
    ):
        """retrieve_semantic is called with the envelope's processed_content."""
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"test","assessment":"test","decisions":[{"type":"respond","text":"Hi","rationale":"greeting","priority":"medium"}],"reflection":{"confidence":0.5,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        envelope = MagicMock()
        envelope.processed_content = "What's Akash's preferred language?"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        await cognitive_core._run_reasoning_cycle(context)

        mock_memory.retrieve_semantic.assert_called_once()
        call_args = mock_memory.retrieve_semantic.call_args
        assert "Akash" in call_args[0][0]


class TestBehavioralPatternsInjection:
    """Test that procedural patterns are injected into the prompt."""

    @pytest.mark.asyncio
    async def test_procedural_patterns_in_prompt(self, cognitive_core, mock_memory):
        """When procedural patterns exist, they appear under BEHAVIORAL PATTERNS."""
        mock_memory.retrieve_procedural.return_value = [
            {
                "description": "Akash prefers concise responses",
                "confidence": 0.8,
                "trigger_context": "when answering questions",
            },
            {
                "description": "System should confirm understanding before acting",
                "confidence": 0.75,
                "trigger_context": "when receiving instructions",
            },
        ]

        envelope = MagicMock()
        envelope.processed_content = "Tell me something"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== BEHAVIORAL PATTERNS ===" in prompt
        assert "Akash prefers concise responses" in prompt
        assert "trigger:" in prompt

    @pytest.mark.asyncio
    async def test_procedural_patterns_omitted_when_empty(self, cognitive_core, mock_memory):
        """When no procedural patterns exist, the section is OMITTED entirely."""
        mock_memory.retrieve_procedural.return_value = []

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== BEHAVIORAL PATTERNS ===" not in prompt
        assert "No patterns" not in prompt

    @pytest.mark.asyncio
    async def test_procedural_patterns_omitted_when_disabled(self, mock_memory):
        """When procedural_enabled=False, section is omitted even if patterns exist."""
        event_bus = EventBus()
        mock_gateway = MagicMock()
        mock_gateway.infer = AsyncMock()
        mock_gateway.shutdown = AsyncMock()

        cc = CognitiveCore(
            config={
                "episodic_memory_enabled": True,
                "semantic_enabled": True,
                "procedural_enabled": False,
            },
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        mock_memory.retrieve_procedural.return_value = [
            {
                "description": "Akash prefers concise responses",
                "confidence": 0.8,
                "trigger_context": "when answering questions",
            },
        ]

        envelope = MagicMock()
        envelope.processed_content = "Tell me something"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cc._assemble_prompt(context, is_daydream=False)

        assert "=== BEHAVIORAL PATTERNS ===" not in prompt

    @pytest.mark.asyncio
    async def test_procedural_patterns_skipped_in_daydream(self, cognitive_core, mock_memory):
        """During daydreaming, procedural patterns are NOT retrieved."""
        mock_memory.retrieve_procedural.return_value = [
            {"description": "Test pattern", "confidence": 0.8, "trigger_context": ""},
        ]

        prompt = await cognitive_core._assemble_prompt(context=None, is_daydream=True)

        mock_memory.retrieve_procedural.assert_not_called()
        assert "=== BEHAVIORAL PATTERNS ===" not in prompt

    @pytest.mark.asyncio
    async def test_procedural_retrieval_called_with_input_text(
        self, cognitive_core, mock_memory, mock_gateway
    ):
        """retrieve_procedural is called with the envelope's processed_content."""
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"test","assessment":"test","decisions":[{"type":"respond","text":"Hi","rationale":"greeting","priority":"medium"}],"reflection":{"confidence":0.5,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        envelope = MagicMock()
        envelope.processed_content = "What's Akash's preferred language?"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        await cognitive_core._run_reasoning_cycle(context)

        mock_memory.retrieve_procedural.assert_called_once()
        call_args = mock_memory.retrieve_procedural.call_args
        assert "Akash" in call_args[0][0]


class TestBothBlocksPresent:
    """Test when both semantic and procedural data are available."""

    @pytest.mark.asyncio
    async def test_both_sections_appear_when_data_exists(
        self, cognitive_core, mock_memory
    ):
        """When both facts and patterns exist, both sections appear in order."""
        mock_memory.retrieve_semantic.return_value = [
            {"statement": "Akash prefers Python", "confidence": 0.85},
        ]
        mock_memory.retrieve_procedural.return_value = [
            {
                "description": "Akash prefers concise responses",
                "confidence": 0.8,
                "trigger_context": "when answering questions",
            },
        ]

        envelope = MagicMock()
        envelope.processed_content = "Tell me something"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" in prompt
        assert "=== BEHAVIORAL PATTERNS ===" in prompt

        # Verify order: CONSOLIDATED KNOWLEDGE comes before BEHAVIORAL PATTERNS
        knowledge_pos = prompt.index("=== CONSOLIDATED KNOWLEDGE ===")
        patterns_pos = prompt.index("=== BEHAVIORAL PATTERNS ===")
        assert knowledge_pos < patterns_pos

    @pytest.mark.asyncio
    async def test_both_sections_omitted_when_both_empty(
        self, cognitive_core, mock_memory
    ):
        """When both are empty, both sections are omitted."""
        mock_memory.retrieve_semantic.return_value = []
        mock_memory.retrieve_procedural.return_value = []

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt
        assert "=== BEHAVIORAL PATTERNS ===" not in prompt


class TestConfigFlags:
    """Test config flag defaults and override behavior."""

    @pytest.mark.asyncio
    async def test_default_flags_are_true(self):
        """Default config has semantic and procedural enabled."""
        event_bus = EventBus()
        mock_gateway = MagicMock()
        mock_gateway.infer = AsyncMock()
        mock_gateway.shutdown = AsyncMock()
        mock_memory = MagicMock()
        mock_memory.retrieve_episodic = AsyncMock(return_value=[])
        mock_memory.retrieve_semantic = AsyncMock(return_value=[])
        mock_memory.retrieve_procedural = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="id")

        # No explicit semantic/procedural flags — defaults should be True
        cc = CognitiveCore(
            config={"episodic_memory_enabled": True},
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        assert cc.semantic_memory_enabled is True
        assert cc.procedural_memory_enabled is True

    @pytest.mark.asyncio
    async def test_explicit_false_disables_retrieval(self, mock_memory):
        """Explicit semantic_enabled=False disables the feature."""
        event_bus = EventBus()
        mock_gateway = MagicMock()
        mock_gateway.infer = AsyncMock()
        mock_gateway.shutdown = AsyncMock()

        cc = CognitiveCore(
            config={
                "episodic_memory_enabled": True,
                "semantic_enabled": False,
                "procedural_enabled": False,
            },
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        assert cc.semantic_memory_enabled is False
        assert cc.procedural_memory_enabled is False


class TestRetrievalExceptions:
    """Test that retrieval exceptions are handled gracefully."""

    @pytest.mark.asyncio
    async def test_semantic_retrieval_exception_does_not_break_prompt(
        self, cognitive_core, mock_memory
    ):
        """If retrieve_semantic raises, the prompt is still assembled."""
        mock_memory.retrieve_semantic = AsyncMock(
            side_effect=RuntimeError("Database error")
        )
        mock_memory.retrieve_procedural = AsyncMock(return_value=[])

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        # Should not raise
        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        # Semantic section should be absent due to the error
        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt
        # Procedural section should also be absent (empty)
        assert "=== BEHAVIORAL PATTERNS ===" not in prompt

    @pytest.mark.asyncio
    async def test_procedural_retrieval_exception_does_not_break_prompt(
        self, cognitive_core, mock_memory
    ):
        """If retrieve_procedural raises, the prompt is still assembled."""
        mock_memory.retrieve_semantic = AsyncMock(return_value=[])
        mock_memory.retrieve_procedural = AsyncMock(
            side_effect=RuntimeError("Database error")
        )

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        # Should not raise
        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "=== CONSOLIDATED KNOWLEDGE ===" not in prompt
        assert "=== BEHAVIORAL PATTERNS ===" not in prompt