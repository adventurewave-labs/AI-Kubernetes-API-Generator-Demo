"""No-op :class:`TelemetrySink`.

See ``docs/ddd/07-anti-corruption-layers.md`` section 6.2 (used by
``--quiet`` mode).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent


class NoopSink:
    """Drop every event. Useful for ``--quiet`` runs and benchmarks."""

    def emit(self, event: DomainEvent) -> None:
        # Intentionally empty: the whole point of this sink is to drop.
        return None

    def flush(self) -> None:
        return None
