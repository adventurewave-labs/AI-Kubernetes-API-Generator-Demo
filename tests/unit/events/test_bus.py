"""Tests for :class:`EventBus` (synchronous in-process pub/sub)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ai_platform_generator.domain.events import DomainEvent, EventBus


def _make(name: str = "IntentSubmitted", context: str = "intent") -> DomainEvent:
    return DomainEvent(
        event_id=uuid4(),
        run_id=None,
        name=name,
        schema_version=1,
        occurred_at=datetime.now(timezone.utc),
        context=context,
        payload={},
        causation_id=None,
    )


def test_publish_delivers_to_each_subscriber_in_order() -> None:
    bus = EventBus()
    seen: list[tuple[str, str]] = []

    bus.subscribe(lambda e: seen.append(("a", e.name)))
    bus.subscribe(lambda e: seen.append(("b", e.name)))

    bus.publish(_make("IntentSubmitted"))
    bus.publish(_make("CommandStarted", context="user_interaction"))

    assert seen == [
        ("a", "IntentSubmitted"),
        ("b", "IntentSubmitted"),
        ("a", "CommandStarted"),
        ("b", "CommandStarted"),
    ]


def test_subscribe_is_idempotent() -> None:
    bus = EventBus()
    seen: list[str] = []
    fn = lambda e: seen.append(e.name)  # noqa: E731

    bus.subscribe(fn)
    bus.subscribe(fn)  # should not double-register

    bus.publish(_make("IntentSubmitted"))
    assert seen == ["IntentSubmitted"]


def test_unsubscribe_removes_subscriber() -> None:
    bus = EventBus()
    seen: list[str] = []
    fn = lambda e: seen.append(e.name)  # noqa: E731

    bus.subscribe(fn)
    bus.unsubscribe(fn)
    bus.publish(_make("IntentSubmitted"))
    assert seen == []

    # Unsubscribing again is a no-op.
    bus.unsubscribe(fn)


def test_subscribe_by_context_filters() -> None:
    bus = EventBus()
    intent_seen: list[str] = []
    cluster_seen: list[str] = []

    bus.subscribe_by_context("intent", lambda e: intent_seen.append(e.name))
    bus.subscribe_by_context("cluster", lambda e: cluster_seen.append(e.name))

    bus.publish(_make("IntentSubmitted", context="intent"))
    bus.publish(_make("ClusterCreationStarted", context="cluster"))
    bus.publish(_make("CommandStarted", context="user_interaction"))

    assert intent_seen == ["IntentSubmitted"]
    assert cluster_seen == ["ClusterCreationStarted"]


def test_subscribe_all_alias_matches_subscribe() -> None:
    # ``subscribe_all`` is a method-level alias for ``subscribe``.
    assert EventBus.subscribe_all is EventBus.subscribe

    bus = EventBus()
    seen: list[str] = []
    bus.subscribe_all(lambda e: seen.append(e.name))
    bus.publish(_make("IntentSubmitted"))
    assert seen == ["IntentSubmitted"]


def test_global_and_context_subscribers_both_fire() -> None:
    bus = EventBus()
    everything: list[str] = []
    only_intent: list[str] = []

    bus.subscribe(lambda e: everything.append(e.name))
    bus.subscribe_by_context("intent", lambda e: only_intent.append(e.name))

    bus.publish(_make("IntentSubmitted", context="intent"))
    bus.publish(_make("ClusterCreationStarted", context="cluster"))

    assert everything == ["IntentSubmitted", "ClusterCreationStarted"]
    assert only_intent == ["IntentSubmitted"]


def test_unsubscribe_context_subscriber() -> None:
    bus = EventBus()
    seen: list[str] = []
    fn = lambda e: seen.append(e.name)  # noqa: E731

    bus.subscribe_by_context("intent", fn)
    bus.unsubscribe(fn)

    bus.publish(_make("IntentSubmitted"))
    assert seen == []


def test_subscriber_exception_does_not_break_dispatch() -> None:
    bus = EventBus()
    seen: list[str] = []

    def bad(_event: DomainEvent) -> None:
        raise RuntimeError("subscriber bug")

    bus.subscribe(bad)
    bus.subscribe(lambda e: seen.append(e.name))

    # Must not raise — second subscriber still receives the event.
    bus.publish(_make("IntentSubmitted"))
    assert seen == ["IntentSubmitted"]


def test_subscriber_count_introspection() -> None:
    bus = EventBus()
    assert bus.subscriber_count == 0

    bus.subscribe(lambda e: None)
    bus.subscribe_by_context("intent", lambda e: None)
    bus.subscribe_by_context("cluster", lambda e: None)
    assert bus.subscriber_count == 3
