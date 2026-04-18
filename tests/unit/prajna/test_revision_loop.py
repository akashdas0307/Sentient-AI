"""Tests for the World Model revision loop (D4).

After D4 extraction of Decision Arbiter, World Model ONLY publishes decision.reviewed.
It does NOT emit decision.approved, decision.vetoed, or cognitive.reprocess.
The Decision Arbiter handles all routing based on decision.reviewed payload.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Test World Model publishes flat decision.reviewed payload (D4 architecture).

    World Model now ONLY publishes decision.reviewed. It does NOT route.
    The Decision Arbiter subscribes to decision.reviewed and routes to:
      - brainstem.output_approved  (verdict: approved | advisory)
      - cognitive.revise_requested (verdict: revision_requested)
      - cognitive.veto_handled     (verdict: vetoed)
    """

    @pytest.mark.asyncio
    async def test_approved_first_pass(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Happy path: decision approved on first review.

        World Model publishes decision.reviewed with verdict=approved.
        It does NOT publish decision.approved directly.
        """
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

        # World Model publishes decision.reviewed (flat payload)
        event_types = [e["event_type"] for e in published_events]
        assert "decision.reviewed" in event_types
        # World Model does NOT publish routing events
        assert "decision.approved" not in event_types
        assert "brainstem.output_approved" not in event_types
        assert "cognitive.reprocess" not in event_types
        assert "cognitive.revise_requested" not in event_types
        assert "decision.vetoed" not in event_types

        # Verify the decision.reviewed payload has verdict=approved
        reviewed_events = [
            e for e in published_events if e["event_type"] == "decision.reviewed"
        ]
        assert len(reviewed_events) == 1
        assert reviewed_events[0]["verdict"] == "approved"

    @pytest.mark.asyncio
    async def test_one_revision_then_approved(
        self, world_model, cognitive_core, event_bus, mock_gateway, published_events
    ):
        """One revision requested, then approved on second pass.

        World Model publishes decision.reviewed with verdict=revision_requested
        on first pass. Decision Arbiter (not World Model) would publish
        cognitive.revise_requested to trigger the next cycle.
        """
        decision = {"type": "respond", "text": "Hello!"}

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

            # World Model publishes decision.reviewed (not cognitive.revise_requested)
            event_types = [e["event_type"] for e in published_events]
            assert "decision.reviewed" in event_types
            assert "cognitive.revise_requested" not in event_types
            assert "cognitive.reprocess" not in event_types

            # Verify the decision.reviewed payload has verdict=revision_requested
            reviewed_events = [
                e for e in published_events if e["event_type"] == "decision.reviewed"
            ]
            assert len(reviewed_events) == 1
            assert reviewed_events[0]["verdict"] == "revision_requested"
            assert reviewed_events[0]["revision_guidance"] == "Make it warmer."

            # Simulate Cognitive Core handling cognitive.revise_requested
            # (published by Decision Arbiter after receiving decision.reviewed)
            revise_payload = {
                "cycle_id": "test_2",
                "decision": decision,
                "revision_count": 1,
                "revision_guidance": "Make it warmer.",
            }

            with patch.object(
                cognitive_core.event_bus, "publish"
            ) as mock_publish:
                with patch.object(
                    cognitive_core, "_parse_response",
                    return_value={
                        "monologue": "thinking",
                        "assessment": "assessing",
                        "decisions": [decision],
                        "reflection": {},
                    }
                ):
                    await cognitive_core._handle_revise_requested(revise_payload)

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

        # After second review (approved), should have decision.reviewed with verdict=approved
        event_types = [e["event_type"] for e in published_events]
        # Two decision.reviewed events: first revision_requested, then approved
        assert event_types.count("decision.reviewed") == 2
        assert "brainstem.output_approved" not in event_types
        assert "decision.approved" not in event_types

    @pytest.mark.asyncio
    async def test_cap_hit_override_to_approved(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """After 2 revision requests (cap hit), World Model publishes decision.reviewed.

        Revision cap logic is now in Decision Arbiter. World Model only reviews.
        This test verifies World Model publishes decision.reviewed with verdict=revision_requested
        when revision_count=2. The Arbiter handles cap escalation (tested separately).
        """
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
            # revision_count=2 means this is the 3rd attempt (cap would be hit in Arbiter)
            await world_model._handle_decision({
                "cycle_id": "test_3",
                "decision": decision,
                "revision_count": 2,
            })

        event_types = [e["event_type"] for e in published_events]

        # World Model publishes decision.reviewed only
        assert "decision.reviewed" in event_types
        # World Model does NOT publish routing events
        assert "cognitive.revise_requested" not in event_types
        assert "cognitive.reprocess" not in event_types
        assert "decision.approved" not in event_types

        # Verify the decision.reviewed payload
        reviewed_events = [
            e for e in published_events if e["event_type"] == "decision.reviewed"
        ]
        assert len(reviewed_events) == 1
        assert reviewed_events[0]["verdict"] == "revision_requested"
        assert reviewed_events[0]["revision_count"] == 2

    @pytest.mark.asyncio
    async def test_vetoed_no_loop(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Vetoed decision: World Model publishes decision.reviewed with verdict=vetoed.

        World Model does NOT publish decision.vetoed directly.
        Decision Arbiter publishes cognitive.veto_handled.
        """
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

        # World Model publishes decision.reviewed
        assert "decision.reviewed" in event_types
        # World Model does NOT publish veto routing event
        assert "cognitive.veto_handled" not in event_types
        assert "decision.vetoed" not in event_types
        # World Model does NOT publish any approved event
        assert "decision.approved" not in event_types
        assert "brainstem.output_approved" not in event_types

        # Verify the decision.reviewed payload
        reviewed_events = [
            e for e in published_events if e["event_type"] == "decision.reviewed"
        ]
        assert len(reviewed_events) == 1
        assert reviewed_events[0]["verdict"] == "vetoed"
        assert reviewed_events[0]["veto_reason"] == "Inappropriate response."

    @pytest.mark.asyncio
    async def test_advisory_no_loop(
        self, world_model, event_bus, mock_gateway, published_events
    ):
        """Advisory verdict: World Model publishes decision.reviewed with verdict=advisory.

        Advisory maps to approved in Decision Arbiter (brainstem.output_approved).
        World Model does NOT publish brainstem.output_approved directly.
        """
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

        # World Model publishes decision.reviewed
        assert "decision.reviewed" in event_types
        # World Model does NOT publish brainstem.output_approved
        assert "brainstem.output_approved" not in event_types
        assert "decision.approved" not in event_types
        assert "cognitive.revise_requested" not in event_types

        # Verify the decision.reviewed payload
        reviewed_events = [
            e for e in published_events if e["event_type"] == "decision.reviewed"
        ]
        assert len(reviewed_events) == 1
        assert reviewed_events[0]["verdict"] == "advisory"
        assert reviewed_events[0]["advisory_notes"] == "Consider being friendlier."

    @pytest.mark.asyncio
    async def test_revision_count_propagates_to_decision_proposed(
        self, cognitive_core, event_bus, mock_gateway, published_events
    ):
        """Cognitive Core includes revision_count in decision.proposed during revise cycle.

        Uses _handle_revise_requested (not the old _handle_reprocess).
        """
        decision = {"type": "respond", "text": "Hello!"}

        # Simulate a revise_requested payload from Decision Arbiter
        revise_payload = {
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
                await cognitive_core._handle_revise_requested(revise_payload)

            # Check what was published
            publish_calls = mock_publish.call_args_list
            proposed_calls = [
                call for call in publish_calls
                if call[0][0] == "decision.proposed"
            ]
            assert len(proposed_calls) >= 1
            last_call = proposed_calls[-1]
            assert last_call[0][1]["revision_count"] == 1