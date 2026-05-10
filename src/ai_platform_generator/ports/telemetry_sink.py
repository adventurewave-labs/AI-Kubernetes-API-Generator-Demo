"""``TelemetrySink`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_platform_generator.domain.events import DomainEvent


@runtime_checkable
class TelemetrySink(Protocol):
    """Receive :class:`DomainEvent` instances and translate them downstream."""

    def emit(self, event: DomainEvent) -> None:
        """Record a single domain event. Must not raise on a healthy sink."""

    def flush(self) -> None:
        """Flush any buffered output. Called at run-end."""
