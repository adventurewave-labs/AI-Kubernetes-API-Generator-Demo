"""Unit tests for :class:`EventDispatcher`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_platform_generator.domain.events.bus import EventBus
from ai_platform_generator.domain.events.envelope import DomainEvent
from ai_platform_generator.domain.observability.dispatcher import (
    EventDispatcher,
    Subscription,
)


class _RecordingSink:
    """Minimal :class:`TelemetrySink` implementation that records every call."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self.flushes: int = 0

    def emit(self, event: DomainEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushes += 1


class _RaisingSink:
    """Sink that always raises on :meth:`emit` — used to test isolation."""

    def __init__(self) -> None:
        self.attempts: int = 0

    def emit(self, event: DomainEvent) -> None:
        self.attempts += 1
        raise RuntimeError("boom")

    def flush(self) -> None:
        raise RuntimeError("flush boom")


def _make_envelope(
    name: str = "X", context: str = "orchestrator"
) -> DomainEvent:
    return DomainEvent(
        event_id=uuid4(),
        run_id=None,
        name=name,
        schema_version=1,
        context=context,
        occurred_at=datetime.now(timezone.utc),
        payload={},
    )


# ---------------------------------------------------------------------------
# Subscription / publish
# ---------------------------------------------------------------------------


def test_subscribe_all_routes_every_event() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    dispatcher.subscribe_all(sink)

    e1 = _make_envelope(name="A", context="orchestrator")
    e2 = _make_envelope(name="B", context="generation")
    dispatcher.publish(e1)
    dispatcher.publish(e2)

    assert sink.events == [e1, e2]


def test_subscribe_with_predicate_filters_events() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    dispatcher.subscribe(lambda e: e.name == "Wanted", sink)

    e_wanted = _make_envelope(name="Wanted", context="orchestrator")
    e_dropped = _make_envelope(name="Dropped", context="orchestrator")
    dispatcher.publish(e_wanted)
    dispatcher.publish(e_dropped)

    assert sink.events == [e_wanted]


def test_subscribe_by_context_filters_by_context() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    dispatcher.subscribe_by_context("generation", sink)

    e_in = _make_envelope(name="A", context="generation")
    e_out = _make_envelope(name="A", context="orchestrator")
    dispatcher.publish(e_in)
    dispatcher.publish(e_out)

    assert sink.events == [e_in]


def test_unsubscribe_removes_handler() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    sub = dispatcher.subscribe_all(sink)

    dispatcher.publish(_make_envelope())
    assert len(sink.events) == 1
    sub.unsubscribe()
    assert dispatcher.subscription_count == 0
    dispatcher.publish(_make_envelope())
    assert len(sink.events) == 1  # no change


def test_unsubscribe_is_idempotent() -> None:
    dispatcher = EventDispatcher()
    sub = dispatcher.subscribe_all(_RecordingSink())
    sub.unsubscribe()
    sub.unsubscribe()  # must not raise


def test_subscription_returns_handle() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    sub = dispatcher.subscribe_all(sink)
    assert isinstance(sub, Subscription)
    assert sub.dispatcher is dispatcher
    assert sub.sink is sink


# ---------------------------------------------------------------------------
# Sink-error isolation
# ---------------------------------------------------------------------------


def test_one_failing_sink_does_not_block_others(capsys: Any) -> None:
    dispatcher = EventDispatcher()
    bad = _RaisingSink()
    good = _RecordingSink()
    dispatcher.subscribe_all(bad)
    dispatcher.subscribe_all(good)

    e = _make_envelope(name="X", context="orchestrator")
    dispatcher.publish(e)

    assert bad.attempts == 1
    assert good.events == [e]
    captured = capsys.readouterr()
    assert "EventDispatcher" in captured.err
    assert "_RaisingSink" in captured.err


def test_predicate_raising_does_not_break_dispatch(capsys: Any) -> None:
    dispatcher = EventDispatcher()
    good = _RecordingSink()

    def _angry_predicate(_event: DomainEvent) -> bool:
        raise RuntimeError("predicate boom")

    dispatcher.subscribe(_angry_predicate, _RecordingSink())
    dispatcher.subscribe_all(good)

    e = _make_envelope()
    dispatcher.publish(e)

    assert good.events == [e]
    captured = capsys.readouterr()
    assert "predicate" in captured.err.lower() or "EventDispatcher" in captured.err


# ---------------------------------------------------------------------------
# Bus delegation
# ---------------------------------------------------------------------------


def test_publish_also_invokes_underlying_bus() -> None:
    bus = EventBus()
    seen: list[DomainEvent] = []
    bus.subscribe_all(seen.append)
    dispatcher = EventDispatcher(bus=bus)

    sink = _RecordingSink()
    dispatcher.subscribe_all(sink)

    e = _make_envelope()
    dispatcher.publish(e)

    assert seen == [e]
    assert sink.events == [e]


def test_dispatcher_constructs_default_bus_when_omitted() -> None:
    dispatcher = EventDispatcher()
    assert isinstance(dispatcher.bus, EventBus)


# ---------------------------------------------------------------------------
# Flush
# ---------------------------------------------------------------------------


def test_flush_calls_each_subscribed_sink_once() -> None:
    dispatcher = EventDispatcher()
    sink = _RecordingSink()
    dispatcher.subscribe_all(sink)
    dispatcher.subscribe_by_context("generation", sink)  # duplicate registration

    dispatcher.flush()
    assert sink.flushes == 1  # de-duplicated by id()


def test_flush_swallows_per_sink_errors(capsys: Any) -> None:
    dispatcher = EventDispatcher()
    bad = _RaisingSink()
    good = _RecordingSink()
    dispatcher.subscribe_all(bad)
    dispatcher.subscribe_all(good)

    dispatcher.flush()
    assert good.flushes == 1
    captured = capsys.readouterr()
    assert "flush failed" in captured.err
