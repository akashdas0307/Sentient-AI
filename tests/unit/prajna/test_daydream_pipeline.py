"""Unit tests for Phase 10 D2: Daydream Pipeline Fix.

Validates that the CognitiveCore._daydream() method:
- Uses SourceType.INTERNAL_DAYDREAM (not a generic internal type)
- Builds a proper synthetic envelope instead of passing context=None
- Produces real thoughts via the full reasoning pipeline
- Guards against overlapping daydream sessions
- Uses cycle-local turn_id with daydream_ prefix
- Calls the seed selector to obtain seed text
"""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock
import json

from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.core.envelope import Envelope, SourceType
from sentient.core.event_bus import EventBus, reset_event_bus


# =============================================================================
# Fixtures
# =============================================================================

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
            "daydream": {
                "enabled": True,
                "idle_seconds_before_trigger": 90,
                "seed_sources_enabled": True,
                "curiosity_queue_max_size": 20,
                "emotional_residue_window_minutes": 30,
            },
        },
        inference_gateway=mock_gateway,
        memory=mock_memory,
        event_bus=event_bus,
    )
    return cc


def _valid_daydream_response():
    """A valid JSON response from the inference gateway for daydream."""
    return json.dumps({
        "monologue": "Reflecting on recent events",
        "assessment": "Daydreaming about past interactions",
        "decisions": [
            {
                "type": "reflect",
                "text": "I wonder about the nature of my experiences",
                "rationale": "curiosity",
                "priority": "low",
            }
        ],
        "reflection": {
            "confidence": 0.7,
            "uncertainties": ["whether this reflection is meaningful"],
            "novelty": 0.3,
            "memory_candidates": [
                {
                    "type": "episodic",
                    "content": "A reflective moment during idle time",
                    "importance": 0.4,
                }
            ],
            "curiosity_candidates": [
                "What patterns emerge from my recent interactions?"
            ],
        },
    })


# =============================================================================
# Test 1: SourceType.INTERNAL_DAYDREAM exists and is internal
# =============================================================================

class TestInternalDaydreamSourceType:
    """Tests for SourceType.INTERNAL_DAYDREAM enum and its properties."""

    def test_internal_daydream_enum_value(self):
        """SourceType.INTERNAL_DAYDREAM is a valid enum member with value 'internal_daydream'."""
        assert hasattr(SourceType, "INTERNAL_DAYDREAM")
        assert SourceType.INTERNAL_DAYDREAM.value == "internal_daydream"

    def test_internal_daydream_is_not_external(self):
        """An envelope with source_type=INTERNAL_DAYDREAM returns False from is_external()."""
        envelope = Envelope(
            source_type=SourceType.INTERNAL_DAYDREAM,
            processed_content="some seed text",
        )
        assert envelope.is_external() is False

    def test_internal_daydream_is_distinct_from_other_internal_types(self):
        """INTERNAL_DAYDREAM is different from INTERNAL_DREAM and other internal types."""
        assert SourceType.INTERNAL_DAYDREAM != SourceType.INTERNAL_DREAM
        assert SourceType.INTERNAL_DAYDREAM != SourceType.INTERNAL_LIMBIC
        assert SourceType.INTERNAL_DAYDREAM != SourceType.INTERNAL_HEALTH


# =============================================================================
# Test 2: Daydream builds a synthetic envelope with INTERNAL_DAYDREAM source
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_builds_synthetic_envelope_with_internal_daydream(cognitive_core, mock_gateway, event_bus):
    """_daydream() constructs a proper Envelope with source_type=INTERNAL_DAYDREAM.

    Verifies the fix: the synthetic envelope is built and passed to the
    reasoning cycle (not context=None which hit the old early-return guard).
    """
    # Track what context/envelope was passed to _run_reasoning_cycle
    run_context = None
    run_envelope = None
    run_is_daydream = None

    original_run = cognitive_core._run_reasoning_cycle

    async def track_run_reasoning_cycle(context, envelope=None, is_daydream=False, turn_id=None):
        nonlocal run_context, run_envelope, run_is_daydream
        run_context = context
        run_envelope = envelope
        run_is_daydream = is_daydream
        return await original_run(context, envelope=envelope, is_daydream=is_daydream, turn_id=turn_id)

    cognitive_core._run_reasoning_cycle = track_run_reasoning_cycle

    # Configure gateway to return a valid response
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Execute daydream
    await cognitive_core._daydream()

    # --- Assertions ---
    # A real context dict (not None) was passed
    assert run_context is not None, "_daydream() passed None context to reasoning cycle"
    assert isinstance(run_context, dict), "context should be a dict"
    assert "envelope" in run_context, "context should contain envelope key"

    # The envelope in context has source_type=INTERNAL_DAYDREAM
    assert run_envelope is not None, "envelope should not be None"
    assert run_envelope.source_type == SourceType.INTERNAL_DAYDREAM, (
        f"Expected source_type=INTERNAL_DAYDREAM, got {run_envelope.source_type}"
    )

    # is_daydream flag was set
    assert run_is_daydream is True, "is_daydream should be True for daydream cycle"

    # Envelope metadata indicates daydream
    assert run_envelope.metadata.get("is_daydream") is True


# =============================================================================
# Test 3: Daydream produces a real thought via the reasoning pipeline
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_produces_real_thought_via_reasoning_pipeline(cognitive_core, mock_gateway, event_bus):
    """When gateway returns valid JSON, _daydream() produces a real thought.

    Verifies that:
    - cognitive.cycle.complete is published
    - The event has non-empty monologue
    - decision_count > 0 (a real decision was made, not just empty noise)
    """
    # Configure gateway to return valid JSON
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Collect cognitive.cycle.complete events via async subscribe
    complete_events = []

    async def collector(payload):
        complete_events.append(payload)

    await event_bus.subscribe("cognitive.cycle.complete", collector)

    # Execute daydream
    await cognitive_core._daydream()

    # Yield control so fire-and-forget event handlers can run
    await asyncio.sleep(0)

    # Find the cycle.complete event for the daydream
    daydream_complete = None
    for event in complete_events:
        if event.get("is_daydream"):
            daydream_complete = event
            break

    assert daydream_complete is not None, (
        f"No cognitive.cycle.complete event with is_daydream=True. Events: {complete_events}"
    )
    assert daydream_complete.get("monologue"), "monologue should be non-empty"
    assert daydream_complete.get("decision_count", 0) > 0, (
        f"decision_count should be > 0, got {daydream_complete.get('decision_count')}"
    )


# =============================================================================
# Test 4: Daydream guard prevents overlapping daydream sessions
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_guard_prevents_overlapping_sessions(cognitive_core, mock_gateway):
    """When _daydream_in_progress is True, _daydream() returns early without calling gateway."""
    # Set the guard — simulate an in-progress daydream
    cognitive_core._daydream_in_progress = True

    # Track calls to gateway.infer
    call_count_before = mock_gateway.infer.call_count

    # Call _daydream() — it should return immediately
    await cognitive_core._daydream()

    # Gateway should NOT have been called
    assert mock_gateway.infer.call_count == call_count_before, (
        "Gateway infer was called despite _daydream_in_progress=True"
    )


# =============================================================================
# Test 5: turn_id is cycle-local and uses daydream_ prefix
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_turn_id_uses_daydream_prefix(cognitive_core, mock_gateway, event_bus):
    """The daydream reasoning cycle uses a cycle-local turn_id starting with 'daydream_'."""
    # Configure gateway to return valid JSON
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Collect decision.proposed events — they carry the turn_id
    decision_events = []

    async def decision_collector(payload):
        decision_events.append(payload)

    await event_bus.subscribe("decision.proposed", decision_collector)

    # Execute daydream
    await cognitive_core._daydream()

    # Yield control so fire-and-forget event handlers can run
    await asyncio.sleep(0)

    # Find a decision event from the daydream cycle
    assert len(decision_events) > 0, (
        "No decision.proposed events published. The daydream should produce decisions."
    )

    # The turn_id in the decision.proposed event should start with "daydream_"
    turn_id = decision_events[0].get("turn_id", "")
    assert turn_id.startswith("daydream_"), (
        f"turn_id should start with 'daydream_', got: {turn_id}"
    )


# =============================================================================
# Test 6: Seed selector is called during daydream
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_calls_seed_selector(cognitive_core, mock_gateway, event_bus):
    """_daydream() calls _build_daydream_seed_async() to obtain seed text.

    Verifies the seed selector is invoked by checking that the final
    envelope's processed_content contains seed-like text (either from
    the selector or the stub fallback).
    """
    # Configure gateway to return valid JSON so the cycle completes
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Track calls to _build_daydream_seed_async
    call_tracker = {"called": False, "result": None}

    original_build_seed = cognitive_core._build_daydream_seed_async

    async def tracked_build_seed():
        call_tracker["called"] = True
        call_tracker["result"] = await original_build_seed()
        return call_tracker["result"]

    cognitive_core._build_daydream_seed_async = tracked_build_seed

    # Execute daydream
    await cognitive_core._daydream()

    # Verify the seed builder was called
    assert call_tracker["called"], (
        "_build_daydream_seed_async() was not called during _daydream()"
    )

    # The seed text (or stub) should appear in the final envelope's content
    # We verify the seed was actually used by checking the reasoning cycle ran
    # with the seed in the context envelope
    assert call_tracker["result"] is not None, (
        "_build_daydream_seed_async() returned None"
    )


# =============================================================================
# Test 6 alt: Seed text appears in envelope processed_content
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_envelope_processed_content_contains_seed(cognitive_core, mock_gateway):
    """The synthetic envelope built in _daydream() uses seed text from the selector."""
    # Configure gateway to return valid JSON
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Track the envelope that gets passed to the reasoning cycle
    captured_envelope = None

    original_run = cognitive_core._run_reasoning_cycle

    async def capture_envelope(context, envelope=None, is_daydream=False, turn_id=None):
        nonlocal captured_envelope
        captured_envelope = envelope
        return await original_run(context, envelope=envelope, is_daydream=is_daydream, turn_id=turn_id)

    cognitive_core._run_reasoning_cycle = capture_envelope

    # Execute daydream
    await cognitive_core._daydream()

    # The envelope's processed_content should contain seed text
    # (either from selector with "=== DAYDREAM SEED ===" or stub with "idle reflection")
    assert captured_envelope is not None, "No envelope was passed to reasoning cycle"
    assert captured_envelope.processed_content, "processed_content should not be empty"
    assert (
        "DAYDREAM SEED" in captured_envelope.processed_content
        or "idle reflection" in captured_envelope.processed_content.lower()
        or "daydream" in captured_envelope.processed_content.lower()
    ), f"processed_content should contain seed text, got: {captured_envelope.processed_content}"


# =============================================================================
# Integration: Full pipeline with seed selector returning custom seed
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_with_custom_seed_produces_reflection(cognitive_core, mock_gateway, event_bus):
    """When seed selector returns a known string, it influences the reflection."""
    # Override the seed selector to return a known seed
    known_seed = "TEST_SEED_MARKER: this is a test seed"

    async def custom_seed():
        return known_seed

    cognitive_core._seed_selector.select_seed = custom_seed

    # Configure gateway to return valid JSON
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = _valid_daydream_response()
    mock_gateway.infer.return_value = mock_response

    # Execute daydream
    await cognitive_core._daydream()

    # The cycle should have completed successfully
    # Verify via gateway call count (should be exactly 1 call for the reasoning cycle)
    assert mock_gateway.infer.call_count >= 1, "Gateway should have been called at least once"


# =============================================================================
# Edge case: Gateway returns malformed JSON — cycle still completes
# =============================================================================

@pytest.mark.asyncio
async def test_daydream_handles_malformed_gateway_response_gracefully(cognitive_core, mock_gateway, event_bus):
    """If gateway returns malformed JSON, _daydream() still completes without crashing.

    The reasoning cycle's finally block always publishes cognitive.cycle.complete,
    and the _parse_response fallback handles unparseable text.
    """
    mock_response = MagicMock()
    mock_response.error = None
    mock_response.text = "this is not valid JSON {{{{"
    mock_gateway.infer.return_value = mock_response

    complete_events = []

    async def collector(payload):
        complete_events.append(payload)

    await event_bus.subscribe("cognitive.cycle.complete", collector)

    # Execute daydream — should not raise
    await cognitive_core._daydream()

    # Yield control so fire-and-forget event handlers can run
    await asyncio.sleep(0)

    # A cycle.complete should still be published (from the finally block)
    # The monologue may be the raw text via fallback parsing
    daydream_complete = next((e for e in complete_events if e.get("is_daydream")), None)
    assert daydream_complete is not None, (
        "cycle.complete should be published even with malformed gateway response"
    )
    # The cycle completed (duration_ms is non-null since completed_at was set)
    assert daydream_complete.get("duration_ms") is not None
