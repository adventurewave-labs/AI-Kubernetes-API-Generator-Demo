"""Recording :class:`TelemetrySink` for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 6.2.

The :class:`RecordingSink` stores every emitted event in an in-memory
list and exposes assertion helpers used by golden / contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent


class RecordingSink:
    """Append every emitted :class:`DomainEvent` to an in-memory list."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self.flushed: int = 0

    # ----- TelemetrySink protocol --------------------------------------

    def emit(self, event: DomainEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushed += 1

    # ----- assertion helpers -------------------------------------------

    def events_with_name(self, name: str) -> list[DomainEvent]:
        """Return every recorded event whose ``name`` matches ``name``."""
        return [e for e in self.events if getattr(e, "name", None) == name]

    def assert_events_in_order(self, *names: str) -> None:
        """Assert ``names`` appear (as a subsequence) in recording order.

        Raises :class:`AssertionError` if the recorded event names do not
        contain ``names`` in the given order. Other event names between
        the requested ones are tolerated (it's a *subsequence* check, not
        an equality check) — but the relative order is enforced.
        """
        actual = [getattr(e, "name", None) for e in self.events]
        idx = 0
        for expected in names:
            try:
                idx = actual.index(expected, idx) + 1
            except ValueError:  # pragma: no cover - exercised in failure test
                raise AssertionError(
                    f"event {expected!r} not found in order; recorded: {actual!r}",
                ) from None

    def clear(self) -> None:
        """Drop all recorded events. Useful between phases of a test."""
        self.events.clear()
