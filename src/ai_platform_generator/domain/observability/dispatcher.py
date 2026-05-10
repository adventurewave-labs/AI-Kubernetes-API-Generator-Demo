"""``EventDispatcher`` — predicate-filtered fan-out over an :class:`EventBus`.

Realises ``docs/ddd/bounded-contexts/06-observability.md`` §5.

The dispatcher wraps a Wave-1 :class:`EventBus` and adds *predicate-based*
subscriptions: each subscriber declares the events it wants via a
callable; the dispatcher walks the registry on every publish and routes
the event to every sink whose predicate fires for it.

This is the seam the composition root uses to wire structured logging,
metrics, and OpenTelemetry sinks. Domain code calls only
:meth:`publish`; the bus's "see every event" subscriptions remain in
place so legacy single-callback subscribers continue to work.

Per-sink errors are swallowed and reported on stderr in the same shape
as :class:`MultiSink` so a misbehaving sink cannot poison the rest.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from ai_platform_generator.domain.events.bus import EventBus
from ai_platform_generator.domain.events.envelope import DomainEvent
from ai_platform_generator.ports.telemetry_sink import TelemetrySink

#: Type alias for a subscription predicate.
Predicate = Callable[[DomainEvent], bool]


@dataclass(slots=True)
class Subscription:
    """Handle returned from :meth:`EventDispatcher.subscribe`.

    Carries the originating dispatcher so callers can drop the
    subscription with :meth:`unsubscribe` without keeping a reference to
    the dispatcher themselves.
    """

    dispatcher: EventDispatcher
    predicate: Predicate
    sink: TelemetrySink

    def unsubscribe(self) -> None:
        """Remove this subscription from the dispatcher.

        Idempotent: calling :meth:`unsubscribe` more than once is a no-op
        on subsequent calls.
        """
        self.dispatcher._remove_subscription(self)


class EventDispatcher:
    """Fan :class:`DomainEvent`s out to predicate-filtered :class:`TelemetrySink`s.

    Parameters
    ----------
    bus:
        Optional underlying :class:`EventBus`. A fresh bus is created
        when not supplied so the dispatcher is usable stand-alone.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus: EventBus = bus if bus is not None else EventBus()
        # ``list`` is sufficient for the small subscription counts we
        # expect in production (a handful of sinks). Order is preserved
        # so test assertions on per-sink call order are stable.
        self._subscriptions: list[Subscription] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def bus(self) -> EventBus:
        """The underlying :class:`EventBus`."""
        return self._bus

    @property
    def subscription_count(self) -> int:
        """Number of active dispatcher-level subscriptions."""
        return len(self._subscriptions)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------
    def subscribe(
        self, predicate: Predicate, sink: TelemetrySink
    ) -> Subscription:
        """Register ``sink`` to receive events matching ``predicate``.

        Returns a :class:`Subscription` that can be used to remove the
        registration via :meth:`Subscription.unsubscribe`.
        """
        sub = Subscription(dispatcher=self, predicate=predicate, sink=sink)
        self._subscriptions.append(sub)
        return sub

    def subscribe_all(self, sink: TelemetrySink) -> Subscription:
        """Sugar for ``dispatcher.subscribe(lambda _: True, sink)``."""
        return self.subscribe(_always_true, sink)

    def subscribe_by_context(
        self, context: str, sink: TelemetrySink
    ) -> Subscription:
        """Sugar for ``dispatcher.subscribe(event.context == context, sink)``."""

        def _by_context(event: DomainEvent) -> bool:
            return event.context == context

        return self.subscribe(_by_context, sink)

    def _remove_subscription(self, sub: Subscription) -> None:
        """Drop ``sub`` from the registry. Called by ``Subscription.unsubscribe``."""
        # ``in`` uses ``__eq__``; identity is what we want here.
        for index, candidate in enumerate(self._subscriptions):
            if candidate is sub:
                del self._subscriptions[index]
                return

    # ------------------------------------------------------------------
    # Publication / flush
    # ------------------------------------------------------------------
    def publish(self, event: DomainEvent) -> None:
        """Deliver ``event`` to the bus *and* every matching sink.

        The bus is published to first so existing single-callback
        subscribers see the event before any predicate-filtered sink
        does. Per-sink errors are caught and printed to stderr in the
        same shape :class:`MultiSink` uses; one bad sink cannot prevent
        another from observing the event.
        """
        # Deliver to the underlying bus (best-effort already inside the bus).
        self._bus.publish(event)

        # Snapshot to tolerate subscribers that mutate the registry mid-dispatch.
        for sub in list(self._subscriptions):
            try:
                if not sub.predicate(event):
                    continue
            except Exception as exc:  # pragma: no cover - logged only
                print(
                    "EventDispatcher: predicate raised on "
                    f"{type(sub.sink).__name__}: {exc!r}",
                    file=sys.stderr,
                )
                continue
            try:
                sub.sink.emit(event)
            except Exception as exc:  # pragma: no cover - logged only
                print(
                    "EventDispatcher: emit failed on "
                    f"{type(sub.sink).__name__}: {exc!r}",
                    file=sys.stderr,
                )

    def flush(self) -> None:
        """Call :meth:`flush` on every subscribed sink (best-effort)."""
        # De-duplicate by ``id`` so a sink subscribed multiple times is
        # only flushed once.
        seen: set[int] = set()
        for sub in list(self._subscriptions):
            sink = sub.sink
            key = id(sink)
            if key in seen:
                continue
            seen.add(key)
            flusher = getattr(sink, "flush", None)
            if flusher is None:
                continue
            try:
                flusher()
            except Exception as exc:  # pragma: no cover - logged only
                print(
                    "EventDispatcher: flush failed on "
                    f"{type(sink).__name__}: {exc!r}",
                    file=sys.stderr,
                )


def _always_true(_event: DomainEvent) -> bool:
    """Module-level predicate so ``subscribe_all`` remains picklable."""
    return True


__all__ = [
    "EventDispatcher",
    "Predicate",
    "Subscription",
]
