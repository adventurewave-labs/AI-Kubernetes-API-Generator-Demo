"""The :class:`Renderer` Protocol.

Per ``docs/ddd/bounded-contexts/05-user-interaction.md`` §5 the renderer is
the *only* place where presentation concerns (Rich, ANSI, JSON encoding)
exist. Application services emit ``DomainEvent``\\ s and call
:meth:`Renderer.error` on failure. Concrete implementations live alongside
this module.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import GenerationSummary
    from ai_platform_generator.domain.errors import PlatformGeneratorError
    from ai_platform_generator.domain.events import DomainEvent


@runtime_checkable
class Renderer(Protocol):
    """A presentation strategy for a single CLI invocation."""

    def begin(self) -> None:
        """Emit the welcome / header content (if any)."""

    def event(self, event: DomainEvent) -> None:
        """Render a single domain event."""

    def end(self, summary: GenerationSummary) -> None:
        """Render the run summary on success."""

    def error(self, error: PlatformGeneratorError) -> int:
        """Render an error and return the corresponding exit code."""


__all__ = ["Renderer"]
