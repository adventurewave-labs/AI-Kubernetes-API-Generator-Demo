"""A minimal in-process event bus.

The bus is the seam between event producers (services, aggregates) and
side-effecting subscribers (logging, metrics, OTEL spans, the orchestrator).
Subscribers are plain callables — no framework, no metaclasses.

**Thread-safety.** This implementation is *not* thread-safe. It assumes the
single-threaded synchronous orchestrator from
``docs/ddd/06-application-services.md``. If a future change introduces
threads or async, replace the subscriber list with a lock-protected
structure. The GIL alone is not sufficient — list mutation during iteration
will raise.

**Delivery semantics.**
* Synchronous: ``publish`` calls each subscriber in registration order and
  returns when all have returned.
* Best-effort: a subscriber that raises is logged-and-skipped so a misbehaving
  subscriber cannot prevent later ones from seeing the event. This matches
  the "subscribers must be idempotent and tolerant" expectation in
  ``docs/ddd/05-domain-events.md`` §6.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from .envelope import DomainEvent

Subscriber = Callable[[DomainEvent], None]

_logger = logging.getLogger(__name__)


class EventBus:
    """Synchronous, single-threaded publish/subscribe bus."""

    def __init__(self) -> None:
        # Generic subscribers: see every event.
        self._subscribers: list[Subscriber] = []
        # Context-filtered subscribers: see events whose ``context`` matches.
        self._by_context: dict[str, list[Subscriber]] = {}

    # ---- subscription management ----------------------------------------

    def subscribe(self, subscriber: Subscriber) -> None:
        """Register ``subscriber`` to receive every published event."""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    # Alias: explicit "I want every event" reads better at call sites.
    subscribe_all = subscribe

    def subscribe_by_context(
        self, context: str, subscriber: Subscriber
    ) -> None:
        """Register ``subscriber`` to receive only events from ``context``."""
        bucket = self._by_context.setdefault(context, [])
        if subscriber not in bucket:
            bucket.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove ``subscriber`` from every bucket it appears in.

        No-op if the subscriber is not registered.
        """
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
        for bucket in self._by_context.values():
            if subscriber in bucket:
                bucket.remove(subscriber)

    # ---- publication ----------------------------------------------------

    def publish(self, event: DomainEvent) -> None:
        """Synchronously deliver ``event`` to every matching subscriber."""
        # Snapshot to tolerate subscribers that mutate the bus mid-dispatch.
        generic = list(self._subscribers)
        ctx_specific = list(self._by_context.get(event.context, ()))
        for subscriber in generic + ctx_specific:
            try:
                subscriber(event)
            except Exception:
                _logger.exception(
                    "event subscriber raised; continuing dispatch",
                    extra={"event_name": event.name, "context": event.context},
                )

    # ---- introspection (test helpers) -----------------------------------

    @property
    def subscriber_count(self) -> int:
        """Total registered subscribers across every bucket."""
        return len(self._subscribers) + sum(
            len(b) for b in self._by_context.values()
        )
