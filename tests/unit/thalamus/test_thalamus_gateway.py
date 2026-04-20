"""Unit tests for Thalamus Gateway — focus on batch lock deadlock fix.

The Thalamus uses asyncio.Lock for batch synchronization. Python's asyncio.Lock
is NOT reentrant — acquiring it twice from the same coroutine causes permanent
deadlock. These tests verify that the snapshot-then-emit pattern prevents
reentrancy deadlocks.
"""
import asyncio

import pytest

from sentient.core.envelope import Envelope, SourceType, TrustLevel
from sentient.core.event_bus import get_event_bus, reset_event_bus
from sentient.thalamus.gateway import Thalamus


def _make_envelope(
    text: str = "hello",
    source_type: SourceType = SourceType.CHAT,
    sender_identity: str = "user",
    trust_level: TrustLevel = TrustLevel.TIER_1_CREATOR,
) -> Envelope:
    return Envelope(
        source_type=source_type,
        sender_identity=sender_identity,
        trust_level=trust_level,
        raw_content={"text": text},
        processed_content=text,
    )


@pytest.fixture
async def thalamus():
    reset_event_bus()
    event_bus = get_event_bus()
    config = {
        "batching": {
            "min_window_seconds": 0.05,
            "default_window_seconds": 0.05,
            "max_window_seconds": 1.0,
        },
        "heuristic_engine": {
            "tier1_keywords": ["emergency", "shutdown"],
        },
    }
    t = Thalamus(config, event_bus)
    await t.initialize()
    await t.start()
    yield t
    await t.shutdown()


class TestBatchLockNoDeadlock:
    """Verify that the snapshot-then-emit pattern prevents asyncio.Lock deadlock.

    Before the fix, _receive_from_plugin held _batch_lock and called
    _maybe_emit_batch (which also acquires _batch_lock) — causing permanent
    deadlock for Tier 2 messages. Similarly, _forward_immediately called
    _emit_current_batch while holding _batch_lock.
    """

    @pytest.mark.asyncio
    async def test_tier2_message_no_deadlock(self, thalamus):
        """Tier 2 message must not deadlock when triggering batch emit.

        This was the primary bug: _receive_from_plugin called
        _maybe_emit_batch inside _batch_lock, causing permanent deadlock.
        The fix moves _maybe_emit_batch outside the lock block.

        The key assertion: the call completes within timeout (no deadlock).
        Whether the batch is emitted depends on elapsed time vs min_window.
        """
        get_event_bus()  # Initialize event bus for the test

        # Tier 2 message: "hello" from creator → TIER_2_ELEVATED
        envelope = _make_envelope("hello")
        # This must complete without deadlock — that's the core fix
        try:
            await asyncio.wait_for(
                thalamus._receive_from_plugin(envelope),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            pytest.fail("Tier 2 message caused deadlock — _receive_from_plugin hung")

        # The envelope was received (not deadlocked)
        assert thalamus._envelopes_received == 1

    @pytest.mark.asyncio
    async def test_tier1_message_no_deadlock(self, thalamus):
        """Tier 1 message must not deadlock when flushing batch.

        _forward_immediately used to call _emit_current_batch while
        holding _batch_lock. The fix snapshots the batch under lock,
        then emits outside the lock.
        """
        event_bus = get_event_bus()
        received = asyncio.Event()
        events = []

        async def on_classified(payload):
            events.append(payload)
            received.set()

        await event_bus.subscribe("input.classified", on_classified)

        # First add a Tier 3 message to the batch
        tier3_envelope = _make_envelope(
            "normal message",
            sender_identity="stranger",
            trust_level=TrustLevel.TIER_3_EXTERNAL,
        )
        # Override to TIER_3 so it goes to batch
        await thalamus._receive_from_plugin(tier3_envelope)

        # Now send a Tier 1 message — should flush the batch and forward immediately
        tier1_envelope = _make_envelope("emergency shutdown")
        tier1_envelope.processed_content = "emergency shutdown"
        await thalamus._receive_from_plugin(tier1_envelope)

        # Wait — if deadlock exists, this hangs
        try:
            await asyncio.wait_for(received.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Tier 1 message caused deadlock — batch flush hung")

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_multiple_tier2_no_deadlock(self, thalamus):
        """Multiple rapid Tier 2 messages must not cause deadlock.

        Sending several Tier 2 messages in sequence exercises the
        _maybe_emit_batch path multiple times. The core assertion
        is that all calls complete without hanging.
        """
        # Send 5 Tier 2 messages rapidly — each triggers _maybe_emit_batch
        for i in range(5):
            envelope = _make_envelope(f"message {i}")
            try:
                await asyncio.wait_for(
                    thalamus._receive_from_plugin(envelope),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                pytest.fail(f"Message {i} caused deadlock in _receive_from_plugin")

        assert thalamus._envelopes_received == 5

    @pytest.mark.asyncio
    async def test_tier1_flushes_pending_batch(self, thalamus):
        """Tier 1 message flushes pending Tier 3 batch, preserving order."""
        event_bus = get_event_bus()
        events = []

        async def on_classified(payload):
            events.append(payload)

        await event_bus.subscribe("input.classified", on_classified)

        # Add Tier 3 messages to batch
        for i in range(3):
            envelope = _make_envelope(
                f"normal {i}",
                sender_identity="stranger",
                trust_level=TrustLevel.TIER_3_EXTERNAL,
            )
            await thalamus._receive_from_plugin(envelope)

        # Send Tier 1 — should flush batch first, then forward immediately
        tier1 = _make_envelope("emergency shutdown")
        tier1.processed_content = "emergency shutdown"
        await thalamus._receive_from_plugin(tier1)

        await asyncio.sleep(0.1)

        # Should have 4 events: 3 batch + 1 immediate
        assert len(events) == 4

    @pytest.mark.asyncio
    async def test_batching_loop_emits(self, thalamus):
        """Batching loop should emit batches after window expires."""
        event_bus = get_event_bus()
        events = []

        async def on_classified(payload):
            events.append(payload)

        await event_bus.subscribe("input.classified", on_classified)

        # Add a Tier 3 message
        envelope = _make_envelope(
            "batched message",
            sender_identity="stranger",
            trust_level=TrustLevel.TIER_3_EXTERNAL,
        )
        await thalamus._receive_from_plugin(envelope)

        # Wait for the batching loop to emit (window is 0.05s, loop checks every 1s)
        # So we wait up to 2s for the batch to be emitted
        try:
            await asyncio.wait_for(
                asyncio.sleep(2.0), timeout=2.5
            )
        except asyncio.TimeoutError:
            pass

        # The batching loop should have emitted the batch
        assert len(events) >= 1


class TestThalamusStats:
    """Verify health metrics are correctly tracked."""

    @pytest.mark.asyncio
    async def test_envelopes_received_counter(self, thalamus):
        envelope = _make_envelope("test")
        await thalamus._receive_from_plugin(envelope)
        assert thalamus._envelopes_received == 1

    @pytest.mark.asyncio
    async def test_duplicate_detection(self, thalamus):
        """Duplicate envelopes should be dropped."""
        envelope = _make_envelope("duplicate")
        await thalamus._receive_from_plugin(envelope)
        await thalamus._receive_from_plugin(envelope)

        # Second call should be dropped as duplicate
        assert thalamus._envelopes_received == 2  # Received counter increments
        # But only one should be forwarded
        # (we can check _recent_envelopes has dedup note)
        assert any(
            "dedup" in str(n)
            for n in envelope.processing_notes
        )


class TestAttentionSummary:
    """Verify attention summary adjusts batching window."""

    @pytest.mark.asyncio
    async def test_active_conversation_shortens_window(self, thalamus):
        event_bus = get_event_bus()
        await event_bus.publish(
            "attention.summary.update",
            {"summary": {"current_focus": "active_conversation"}},
        )
        await asyncio.sleep(0.05)
        assert thalamus.current_window == thalamus.min_window

    @pytest.mark.asyncio
    async def test_idle_widens_window(self, thalamus):
        event_bus = get_event_bus()
        await event_bus.publish(
            "attention.summary.update",
            {"summary": {"current_focus": "idle"}},
        )
        await asyncio.sleep(0.05)
        assert thalamus.current_window == thalamus.max_window