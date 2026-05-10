"""Composite :class:`TelemetrySink` that fans events out to N sinks.

See ``docs/ddd/07-anti-corruption-layers.md`` section 6.2.

A single faulty sink must not break the rest. We swallow per-sink
exceptions and report them via ``print(..., file=sys.stderr)`` for now;
a structured stderr logger will replace this in Phase 5 (per the
implementation roadmap).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent
    from ai_platform_generator.ports.telemetry_sink import TelemetrySink


class MultiSink:
    """Fan an event out to a list of inner sinks.

    On ``emit`` and ``flush`` we iterate the inner sinks in order and
    swallow any exception so a misbehaving sink cannot poison the
    others. Errors are written to ``stderr`` so they remain visible
    without an established logger.
    """

    def __init__(self, sinks: Iterable[TelemetrySink] | None = None) -> None:
        self._sinks: list[TelemetrySink] = list(sinks or ())

    @property
    def sinks(self) -> list[TelemetrySink]:
        return list(self._sinks)

    def add(self, sink: TelemetrySink) -> None:
        self._sinks.append(sink)

    # ----- TelemetrySink protocol --------------------------------------

    def emit(self, event: DomainEvent) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception as exc:  # pragma: no cover - logged only
                print(
                    f"MultiSink: emit failed on {type(sink).__name__}: {exc!r}",
                    file=sys.stderr,
                )

    def flush(self) -> None:
        for sink in self._sinks:
            try:
                sink.flush()
            except Exception as exc:  # pragma: no cover - logged only
                print(
                    f"MultiSink: flush failed on {type(sink).__name__}: {exc!r}",
                    file=sys.stderr,
                )
