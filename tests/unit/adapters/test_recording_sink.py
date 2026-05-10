"""Tests for :class:`RecordingSink`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_platform_generator.adapters.telemetry.recording import RecordingSink


def _ev(name: str) -> SimpleNamespace:
    """Build an event-shaped stub with just enough surface for the sink.

    The :class:`RecordingSink` only inspects ``event.name`` so a
    ``SimpleNamespace`` is sufficient and keeps the test independent of
    the real :class:`DomainEvent` envelope.
    """
    return SimpleNamespace(name=name)


def test_emit_records_events_in_order() -> None:
    sink = RecordingSink()
    sink.emit(_ev("A"))
    sink.emit(_ev("B"))
    sink.emit(_ev("C"))

    assert [e.name for e in sink.events] == ["A", "B", "C"]


def test_events_with_name_filters() -> None:
    sink = RecordingSink()
    sink.emit(_ev("A"))
    sink.emit(_ev("B"))
    sink.emit(_ev("A"))

    assert len(sink.events_with_name("A")) == 2
    assert sink.events_with_name("missing") == []


def test_assert_events_in_order_subsequence_passes() -> None:
    sink = RecordingSink()
    for n in ("A", "X", "B", "Y", "C"):
        sink.emit(_ev(n))

    sink.assert_events_in_order("A", "B", "C")
    sink.assert_events_in_order("A", "C")  # subsequence is fine


def test_assert_events_in_order_failure() -> None:
    sink = RecordingSink()
    sink.emit(_ev("A"))
    sink.emit(_ev("B"))

    with pytest.raises(AssertionError, match="not found"):
        sink.assert_events_in_order("A", "B", "C")

    # Wrong order: B-then-A in recording, asserting A-then-B-then-A fails
    # on the trailing A.
    sink2 = RecordingSink()
    sink2.emit(_ev("B"))
    sink2.emit(_ev("A"))
    with pytest.raises(AssertionError):
        sink2.assert_events_in_order("A", "B")


def test_flush_increments_counter() -> None:
    sink = RecordingSink()
    sink.flush()
    sink.flush()
    assert sink.flushed == 2


def test_clear_drops_recorded_events() -> None:
    sink = RecordingSink()
    sink.emit(_ev("A"))
    sink.clear()
    assert sink.events == []
