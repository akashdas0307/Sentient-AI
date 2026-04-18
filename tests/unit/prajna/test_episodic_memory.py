"""Tests for episodic memory integration in Cognitive Core (D4)."""
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
    mem.store = AsyncMock(return_value="test-memory-id")
    return mem


@pytest.fixture
def cognitive_core(event_bus, mock_gateway, mock_memory):
    cc = CognitiveCore(
        config={"episodic_memory_enabled": True},
        inference_gateway=mock_gateway,
        memory=mock_memory,
        event_bus=event_bus,
    )
    return cc


class TestEpisodicMemoryRetrieval:
    """Test that episodic memories are included in the prompt."""

    @pytest.mark.asyncio
    async def test_retrieve_episodic_called_in_assemble_prompt(
        self, cognitive_core, mock_memory, mock_gateway
    ):
        """When memory is available and enabled, retrieve_episodic is called."""
        envelope = MagicMock()
        envelope.processed_content = "Hello, I'm Akash"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        # Set up mock gateway response
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"test","assessment":"test","decisions":[{"type":"respond","text":"Hi","rationale":"greeting","priority":"medium"}],"reflection":{"confidence":0.5,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        await cognitive_core._run_reasoning_cycle(context)

        # Verify retrieve_episodic was called with the input text
        mock_memory.retrieve_episodic.assert_called_once()
        call_args = mock_memory.retrieve_episodic.call_args
        assert "Akash" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_memory_not_retrieved_when_disabled(
        self, event_bus, mock_gateway, mock_memory
    ):
        """When episodic_memory_enabled=False, no retrieval occurs."""
        cc = CognitiveCore(
            config={"episodic_memory_enabled": False},
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"test","assessment":"test","decisions":[{"type":"respond","text":"Hi","rationale":"greeting","priority":"medium"}],"reflection":{"confidence":0.5,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        await cc._run_reasoning_cycle(context)

        mock_memory.retrieve_episodic.assert_not_called()

    @pytest.mark.asyncio
    async def test_episodic_memories_included_in_prompt(
        self, cognitive_core, mock_memory
    ):
        """When episodic memories exist, they appear in the assembled prompt."""
        mock_memory.retrieve_episodic.return_value = [
            {"content": "Akash introduced themselves", "importance": 0.9, "processed_content": "Akash introduced themselves"},
        ]

        envelope = MagicMock()
        envelope.processed_content = "What's my name?"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "RECENT EPISODIC MEMORY" in prompt
        assert "Akash" in prompt

    @pytest.mark.asyncio
    async def test_no_memory_block_when_empty(
        self, cognitive_core, mock_memory
    ):
        """When no episodic memories exist, no memory block is added."""
        mock_memory.retrieve_episodic.return_value = []

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        prompt = await cognitive_core._assemble_prompt(context, is_daydream=False)

        assert "RECENT EPISODIC MEMORY" not in prompt


class TestEpisodicMemoryStorage:
    """Test that episodic memories are stored after reasoning cycles."""

    @pytest.mark.asyncio
    async def test_memory_stored_after_successful_cycle(
        self, cognitive_core, mock_memory, mock_gateway
    ):
        """After a successful reasoning cycle, the turn is stored as episodic memory."""
        # Use a proper mock with real attribute access instead of MagicMock
        # to avoid infinite recursion in event bus serialization
        from unittest.mock import PropertyMock
        envelope = MagicMock()
        type(envelope).processed_content = PropertyMock(return_value="Hi, I'm Akash")
        type(envelope).envelope_id = PropertyMock(return_value="test-envelope-id")

        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"A greeting","assessment":"First contact","decisions":[{"type":"respond","text":"Hello Akash!","rationale":"greeting","priority":"high"}],"reflection":{"confidence":0.8,"uncertainties":[],"novelty":0.7,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        # Make store return an awaitable
        mock_memory.store = AsyncMock(return_value="test-memory-id")
        mock_memory.retrieve_episodic = AsyncMock(return_value=[])

        await cognitive_core._run_reasoning_cycle(context)

        # Verify memory.store was called
        mock_memory.store.assert_called_once()
        call_kwargs = mock_memory.store.call_args[0][0]
        assert call_kwargs["type"] == "episodic"
        assert "Akash" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_memory_not_stored_on_daydream(
        self, cognitive_core, mock_memory
    ):
        """Daydream cycles should NOT store episodic memory."""
        # Daydream with no context/envelope
        await cognitive_core._run_reasoning_cycle(context=None, is_daydream=True)

        mock_memory.store.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_not_stored_when_disabled(
        self, event_bus, mock_gateway, mock_memory
    ):
        """When episodic_memory_enabled=False, no storage occurs."""
        cc = CognitiveCore(
            config={"episodic_memory_enabled": False},
            inference_gateway=mock_gateway,
            memory=mock_memory,
            event_bus=event_bus,
        )

        envelope = MagicMock()
        envelope.processed_content = "Hello"
        context = SimpleNamespace(
            envelope=envelope,
            related_memories=[],
            significance={},
            sidebar=[],
        )

        mock_response = MagicMock()
        mock_response.error = None
        mock_response.text = '{"monologue":"test","assessment":"test","decisions":[{"type":"respond","text":"Hi","rationale":"greeting","priority":"medium"}],"reflection":{"confidence":0.5,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
        mock_gateway.infer.return_value = mock_response

        await cc._run_reasoning_cycle(context)

        mock_memory.store.assert_not_called()


class TestMemoryArchitectureRetrieveEpisodic:
    """Test the retrieve_episodic convenience method on MemoryArchitecture."""

    @pytest.mark.asyncio
    async def test_retrieve_episodic_filters_by_type(self):
        """retrieve_episodic should filter for EPISODIC memory type."""
        from sentient.memory.architecture import MemoryArchitecture, MemoryType

        mem = MemoryArchitecture({"embeddings": {"model": "test"}}, event_bus=MagicMock())

        # Mock the retrieve method
        mem.retrieve = AsyncMock(return_value=[
            {"content": "episodic memory", "memory_type": "episodic"},
        ])

        results = await mem.retrieve_episodic("test query", k=3)

        mem.retrieve.assert_called_once_with(
            query="test query",
            memory_types=[MemoryType.EPISODIC],
            limit=3,
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_episodic_handles_exception(self):
        """retrieve_episodic returns empty list on failure."""
        from sentient.memory.architecture import MemoryArchitecture

        mem = MemoryArchitecture({"embeddings": {"model": "test"}}, event_bus=MagicMock())

        # Mock retrieve to raise an exception
        mem.retrieve = AsyncMock(side_effect=RuntimeError("DB error"))

        results = await mem.retrieve_episodic("test query", k=3)

        assert results == []
