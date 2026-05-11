"""Deterministic :class:`Clock` adapter for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 7.2.

``FrozenClock`` is constructed at a chosen ``datetime`` and does not
move until :meth:`advance` is called. ``monotonic()`` returns a
synthetic float whose epoch is the construction time and which only
moves forward when :meth:`advance` is called.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FrozenClock:
    """A frozen-time clock that only advances on demand."""

    def __init__(self, initial: datetime | None = None) -> None:
        if initial is None:
            initial = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        if initial.tzinfo is None:
            # Force UTC so callers cannot accidentally compare aware vs
            # naive datetimes — the port contract is "timezone-aware UTC".
            initial = initial.replace(tzinfo=UTC)
        self._now: datetime = initial
        self._monotonic: float = 0.0

    # ----- Clock protocol ----------------------------------------------

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    # ----- test API ----------------------------------------------------

    def advance(self, delta: timedelta) -> None:
        """Advance both ``now`` and ``monotonic`` by ``delta``.

        ``delta`` must be a non-negative :class:`timedelta` — going
        backwards would violate the monotonic contract and is rejected.
        """
        if delta.total_seconds() < 0:
            raise ValueError("FrozenClock cannot move backwards")
        self._now = self._now + delta
        self._monotonic += delta.total_seconds()
