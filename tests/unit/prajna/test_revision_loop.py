"""Tests for the World Model revision loop (D3)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from sentient.prajna.frontal.world_model import WorldModel, ReviewVerdict
from sentient.prajna.frontal.cognitive_core import CognitiveCore
from sentient.core.event_bus import EventBus, reset_event_bus


@pytest.fixture
def event_bus():
    """Fresh event bus for each test."""
    reset_event_bus()
    return EventBus()


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.infer = AsyncMock(return_value=MagicMock(error=None, text="{}"))
    gw.shutdown = AsyncMock()
    return gw


@pytest.fixture
def world_model(event_bus, mock_gateway):
    wm = WorldModel({}, mock_gateway, event_bus=event_bus)
    return wm


@pytest.fixture
def cognitive_core(event_bus, mock_gateway):
    cc = CognitiveCore({}, mock_gateway, event_bus=event_bus)
    return cc


@pytest.fixture
def published_events(event_bus):
    """Capture all published events."""
    events = []

    original_publish = event_bus.publish

    async def capturing_publish(event_type, payload=None):
        if payload is None:
            payload = {}
        full_payload = {"event_type": event_type, **payload}
        events.append(full_payload)
        await original_publish(event_type, payload)

    event_bus.publish = capturing_publish
    return events


class TestWorldModelRevisionLoop:
    """Test the World Model revision loop with cap at 2 revisions."""

    @pytest.mark.asyncio
    async def test_approved_first_pass(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Happy path: decision approved on first review."""
        verdict = ReviewVerdict(
            cycle_id="test_1",
            decision={"type": "respond", "text": "Hello!"},
            verdict="approved",
            confidence=0.9,
            advisory_notes="Looks good.",
        )

        with patch.object(world_model, "_review", new=AsyncMock(return_value=verdict)):
            await world_model._handle_decision({
                "cycle_id": "test_1",
                "decision": {"type": "respond", "text": "Hello!"},
                "revision_count": 0,
            })

        # Should publish decision.approved
        event_types = [e["event_type"] for e in published_events]
        assert "decision.approved" in event_types
        # Should NOT publish cognitive.reprocess
        assert "cognitive.reprocess" not in event_types
        # Should NOT publish decision.vetoed
        assert "decision.vetoed" not in event_types

    @pytest.mark.asyncio
    async def test_one_revision_then_approved(
        self, world_model, cognitive_core, event_bus, mock_gateway, published_events
    ):
        """One revision requested, then approved on second pass."""
        decision = {"type": "respond", "text": "Hello!"}

        # First call: revision_requested, second call: approved
        revision_verdict = ReviewVerdict(
            cycle_id="test_2",
            decision=decision,
            verdict="revision_requested",
            confidence=0.6,
            revision_guidance="Make it warmer.",
        )
        approved_verdict = ReviewVerdict(
            cycle_id="test_2",
            decision=decision,
            verdict="approved",
            confidence=0.85,
            advisory_notes="Better!",
        )

        call_count = 0

        async def mock_review(cycle_id, decision):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return revision_verdict
            return approved_verdict

        with patch.object(world_model, "_review", new=mock_review):
            # First review: revision_requested
            await world_model._handle_decision({
                "cycle_id": "test_2",
                "decision": decision,
                "revision_count": 0,
            })

            # Should have published cognitive.reprocess
            event_types = [e["event_type"] for e in published_events]
            assert "cognitive.reprocess" in event_types

            # Find the reprocess event and verify its payload
            reprocess_events = [
                e for e in published_events if e["event_type"] == "cognitive.reprocess"
            ]
            assert len(reprocess_events) == 1
            reproc_payload = reprocess_events[0]
            assert reproc_payload["revision_count"] == 1
            assert reproc_payload["decision"] == decision
            assert "revision_guidance" in reproc_payload

            # Simulate Cognitive Core handling reprocess
            # Mock at the event_bus.publish level to capture calls
            with patch.object(
                cognitive_core.event_bus, "publish"
            ) as mock_publish:
                # Mock _parse_response to return structured data with decisions
                with patch.object(
                    cognitive_core, "_parse_response",
                    return_value={
                        "monologue": "thinking",
                        "assessment": "assessing",
                        "decisions": [decision],
                        "reflection": {},
                    }
                ):
                    await cognitive_core._handle_reprocess(reproc_payload)

                # Cognitive Core should have published decision.proposed with revision_count=1
                publish_calls = mock_publish.call_args_list
                proposed_calls = [
                    call for call in publish_calls
                    if call[0][0] == "decision.proposed"
                ]
                assert len(proposed_calls) >= 1
                last_call = proposed_calls[-1]
                assert last_call[0][1]["revision_count"] == 1

            # Now simulate World Model reviewing again with revision_count=1
            # to verify it transitions to approved
            await world_model._handle_decision({
                "cycle_id": "test_2",
                "decision": decision,
                "revision_count": 1,
            })

        # After second review (approved), should have decision.approved
        event_types = [e["event_type"] for e in published_events]
        assert "decision.approved" in event_types

    @pytest.mark.asyncio
    async def test_cap_hit_override_to_approved(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """After 2 revision requests, override to approved."""
        decision = {"type": "respond", "text": "Hello!"}

        verdict = ReviewVerdict(
            cycle_id="test_3",
            decision=decision,
            verdict="revision_requested",
            confidence=0.5,
            advisory_notes="Still needs work.",
            revision_guidance="Try harder.",
        )

        with patch.object(world_model, "_review", new=AsyncMock(return_value=verdict)):
            # revision_count=2 means this is the 3rd attempt (cap hit)
            await world_model._handle_decision({
                "cycle_id": "test_3",
                "decision": decision,
                "revision_count": 2,
            })

        event_types = [e["event_type"] for e in published_events]

        # Should NOT publish cognitive.reprocess (cap hit)
        assert "cognitive.reprocess" not in event_types

        # Should publish decision.approved with advisory notes about cap
        assert "decision.approved" in event_types

        approved_events = [
            e for e in published_events if e["event_type"] == "decision.approved"
        ]
        assert len(approved_events) == 1
        assert "Revision cap exceeded" in approved_events[0]["advisory_notes"]

    @pytest.mark.asyncio
    async def test_vetoed_no_loop(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Vetoed decision propagates without loop."""
        decision = {"type": "respond", "text": "Hello!"}

        verdict = ReviewVerdict(
            cycle_id="test_4",
            decision=decision,
            verdict="vetoed",
            confidence=0.3,
            veto_reason="Inappropriate response.",
        )

        with patch.object(world_model, "_review", new=AsyncMock(return_value=verdict)):
            await world_model._handle_decision({
                "cycle_id": "test_4",
                "decision": decision,
                "revision_count": 0,
            })

        event_types = [e["event_type"] for e in published_events]

        # Should publish decision.vetoed
        assert "decision.vetoed" in event_types

        # Should NOT publish cognitive.reprocess (no loop for veto)
        assert "cognitive.reprocess" not in event_types

        # Should NOT publish decision.approved
        assert "decision.approved" not in event_types

    @pytest.mark.asyncio
    async def test_advisory_no_loop(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Advisory verdict routes to approved without loop."""
        decision = {"type": "respond", "text": "Hello!"}

        verdict = ReviewVerdict(
            cycle_id="test_5",
            decision=decision,
            verdict="advisory",
            confidence=0.7,
            advisory_notes="Consider being friendlier.",
        )

        with patch.object(world_model, "_review", new=AsyncMock(return_value=verdict)):
            await world_model._handle_decision({
                "cycle_id": "test_5",
                "decision": decision,
                "revision_count": 0,
            })

        event_types = [e["event_type"] for e in published_events]

        # Should publish decision.approved (advisory maps to approved)
        assert "decision.approved" in event_types

        # Should NOT publish cognitive.reprocess
        assert "cognitive.reprocess" not in event_types

    @pytest.mark.asyncio
    async def test_revision_count_propagates_to_decision_proposed(
        self, cognitive_core, event_bus, mock_gateway, published_events
    ):
        """Cognitive Core includes revision_count in decision.proposed during reprocess."""
        decision = {"type": "respond", "text": "Hello!"}

        # Simulate a reprocess payload
        reprocess_payload = {
            "cycle_id": "test_6",
            "decision": decision,
            "revision_count": 1,
            "revision_guidance": "Be warmer.",
        }

        # Mock at the event_bus.publish level to capture calls made by _run_reasoning_cycle
        with patch.object(
            cognitive_core.event_bus, "publish"
        ) as mock_publish:
            # Mock _parse_response to return structured data with decisions
            with patch.object(
                cognitive_core, "_parse_response",
                return_value={
                    "monologue": "thinking",
                    "assessment": "assessing",
                    "decisions": [decision],
                    "reflection": {},
                }
            ):
                await cognitive_core._handle_reprocess(reprocess_payload)

            # Check what was published
            publish_calls = mock_publish.call_args_list
            proposed_calls = [
                call for call in publish_calls
                if call[0][0] == "decision.proposed"
            ]
            assert len(proposed_calls) >= 1
            last_call = proposed_calls[-1]
            assert last_call[0][1]["revision_count"] == 1
