"""Unit tests for the Daydream Seed Engine.

Covers: RandomMemorySeed, EmotionalResidueSeed, CuriositySeed, DaydreamSeedSelector.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from sentient.prajna.frontal.daydream_seeds import (
    DaydreamSeed,
    RandomMemorySeed,
    EmotionalResidueSeed,
    CuriositySeed,
    DaydreamSeedSelector,
)


# =============================================================================
# RandomMemorySeed tests
# =============================================================================

@pytest.mark.asyncio
async def test_random_memory_seed_returns_content():
    """When episodic memories exist, get_seed returns content."""
    mock_memory = MagicMock()
    now = 1000.0
    mock_memory.retrieve_episodic = AsyncMock(return_value=[
        {"content": "I spoke with Akash about architecture", "importance": 0.9, "created_at": now - 3600},
        {"content": "Minor idea about threading", "importance": 0.3, "created_at": now - 7200},
    ])

    seed = RandomMemorySeed(mock_memory)
    result = await seed.get_seed()

    assert result is not None
    assert "I spoke with Akash" in result or "Minor idea" in result
    assert result.startswith("(memory trigger)")


@pytest.mark.asyncio
async def test_random_memory_seed_returns_none_on_cold_start():
    """When no episodic memories exist, get_seed returns None."""
    mock_memory = MagicMock()
    mock_memory.retrieve_episodic = AsyncMock(return_value=[])

    seed = RandomMemorySeed(mock_memory)
    result = await seed.get_seed()

    assert result is None


@pytest.mark.asyncio
async def test_random_memory_seed_weights_by_importance():
    """Higher-importance memories are selected more often."""
    mock_memory = MagicMock()
    now = 1000.0
    # Same recency, different importance
    memories = [
        {"content": "high importance", "importance": 0.9, "created_at": now - 3600},
        {"content": "low importance", "importance": 0.1, "created_at": now - 3600},
    ]
    mock_memory.retrieve_episodic = AsyncMock(return_value=memories)

    seed = RandomMemorySeed(mock_memory)
    result = await seed.get_seed()

    assert result is not None
    assert "high importance" in result


# =============================================================================
# EmotionalResidueSeed tests
# =============================================================================

@pytest.mark.asyncio
async def test_emotional_residue_seed_prefers_emotional():
    """Memories with emotional tags in the window are preferred."""
    mock_memory = MagicMock()
    now = 1000.0
    mock_memory.retrieve = AsyncMock(return_value=[
        {
            "content": "joyful moment with Akash",
            "created_at": now - 600,
            "emotional_tags": {"joy": 0.8},
        },
        {
            "content": "neutral conversation",
            "created_at": now - 600,
            "emotional_tags": {},
        },
    ])

    seed = EmotionalResidueSeed(mock_memory, window_minutes=30)
    result = await seed.get_seed()

    assert result is not None
    assert "joyful moment" in result
    assert result.startswith("(emotional residue)")


@pytest.mark.asyncio
async def test_emotional_residue_falls_back_to_recent():
    """When no emotional tags found, falls back to most recent memory."""
    mock_memory = MagicMock()
    now = 1000.0
    mock_memory.retrieve = AsyncMock(return_value=[
        {"content": "neutral memory", "created_at": now - 600, "emotional_tags": {}},
        {"content": "older neutral memory", "created_at": now - 3600, "emotional_tags": {}},
    ])

    seed = EmotionalResidueSeed(mock_memory, window_minutes=30)
    result = await seed.get_seed()

    assert result is not None
    assert "neutral memory" in result


@pytest.mark.asyncio
async def test_emotional_residue_returns_none_on_empty():
    """When no memories at all, returns None."""
    mock_memory = MagicMock()
    mock_memory.retrieve = AsyncMock(return_value=[])

    seed = EmotionalResidueSeed(mock_memory, window_minutes=30)
    result = await seed.get_seed()

    assert result is None


# =============================================================================
# CuriositySeed tests
# =============================================================================

@pytest.mark.asyncio
async def test_curiosity_seed_fifo_queue():
    """Items are returned in FIFO order."""
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    seed = CuriositySeed(mock_bus, max_size=20)

    seed.add_curiosity("first question")
    seed.add_curiosity("second question")
    seed.add_curiosity("third question")

    first = await seed.get_seed()
    second = await seed.get_seed()
    third = await seed.get_seed()

    assert first == "first question"
    assert second == "second question"
    assert third == "third question"


@pytest.mark.asyncio
async def test_curiosity_seed_returns_none_when_empty():
    """Empty queue returns None from get_seed."""
    mock_bus = MagicMock()
    seed = CuriositySeed(mock_bus, max_size=20)

    result = await seed.get_seed()
    assert result is None


@pytest.mark.asyncio
async def test_curiosity_seed_respects_max_size():
    """When queue exceeds max_size, oldest item is dropped."""
    mock_bus = MagicMock()
    seed = CuriositySeed(mock_bus, max_size=3)

    seed.add_curiosity("item 1")
    seed.add_curiosity("item 2")
    seed.add_curiosity("item 3")
    seed.add_curiosity("item 4")  # oldest should be dropped

    first = await seed.get_seed()
    assert first == "item 2"  # item 1 was dropped

    second = await seed.get_seed()
    third = await seed.get_seed()
    fourth = await seed.get_seed()

    assert second == "item 3"
    assert third == "item 4"
    assert fourth is None  # queue exhausted


@pytest.mark.asyncio
async def test_curiosity_seed_no_duplicate():
    """Adding the same question twice does not duplicate."""
    mock_bus = MagicMock()
    seed = CuriositySeed(mock_bus, max_size=5)

    seed.add_curiosity("same question")
    seed.add_curiosity("same question")

    result1 = await seed.get_seed()
    result2 = await seed.get_seed()

    assert result1 == "same question"
    assert result2 is None


# =============================================================================
# DaydreamSeedSelector tests
# =============================================================================

@pytest.mark.asyncio
async def test_selector_cycles_through_sources():
    """Selector calls each source in random order until one succeeds."""
    source1 = MagicMock(spec=DaydreamSeed)
    source1.get_seed = AsyncMock(return_value=None)
    source2 = MagicMock(spec=DaydreamSeed)
    source2.get_seed = AsyncMock(return_value="seed from source 2")
    source3 = MagicMock(spec=DaydreamSeed)
    source3.get_seed = AsyncMock(return_value=None)

    selector = DaydreamSeedSelector([source1, source2, source3])
    result = await selector.select_seed()

    assert result == "seed from source 2"
    # source1 and source3 were called (in some order) but not source2 twice


@pytest.mark.asyncio
async def test_selector_falls_back_to_stub():
    """When all sources return None, stub text is returned."""
    source1 = MagicMock(spec=DaydreamSeed)
    source1.get_seed = AsyncMock(return_value=None)
    source2 = MagicMock(spec=DaydreamSeed)
    source2.get_seed = AsyncMock(return_value=None)

    selector = DaydreamSeedSelector([source1, source2])
    result = await selector.select_seed()

    assert "=== DAYDREAM SEED ===" in result


@pytest.mark.asyncio
async def test_selector_empty_sources_uses_stub():
    """Selector with no sources falls back to stub immediately."""
    selector = DaydreamSeedSelector([])
    result = await selector.select_seed()

    assert "=== DAYDREAM SEED ===" in result


@pytest.mark.asyncio
async def test_selector_custom_stub():
    """Custom stub text can be provided."""
    source1 = MagicMock(spec=DaydreamSeed)
    source1.get_seed = AsyncMock(return_value=None)

    selector = DaydreamSeedSelector([source1], stub_text="custom stub text")
    result = await selector.select_seed()

    assert result == "custom stub text"


# =============================================================================
# Curiosity candidates extraction integration test
# =============================================================================

@pytest.mark.asyncio
async def test_curiosity_candidates_extracted_from_reflection():
    """Verify that a parsed reflection with curiosity_candidates is correctly handled.

    This is a logic test: given a reflection dict with curiosity_candidates,
    the CognitiveCore should add each to the curiosity seed queue.
    """
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    seed = CuriositySeed(mock_bus, max_size=20)

    reflection = {
        "confidence": 0.85,
        "uncertainties": [],
        "novelty": 0.6,
        "memory_candidates": [],
        "curiosity_candidates": [
            "What would happen if I explored the memory architecture more?",
            "Why does Akash prefer that specific approach?",
        ],
    }

    # Simulate what cognitive_core does after parsing the response
    curiosity_candidates = reflection.get("curiosity_candidates", [])
    for question in curiosity_candidates:
        seed.add_curiosity(question)

    # Verify both were queued
    first = await seed.get_seed()
    second = await seed.get_seed()
    third = await seed.get_seed()

    assert first == "What would happen if I explored the memory architecture more?"
    assert second == "Why does Akash prefer that specific approach?"
    assert third is None  # queue empty after two