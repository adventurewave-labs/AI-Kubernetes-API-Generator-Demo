"""``RunRepository`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 8 and
``docs/ddd/04-tactical-design.md`` section 6.2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_platform_generator.domain.aggregates import GenerationRun
    from ai_platform_generator.domain.values import RunId


@runtime_checkable
class RunRepository(Protocol):
    """Append-only store of :class:`GenerationRun` entities."""

    def append(self, run: GenerationRun) -> None:
        """Persist ``run``. Implementations are append-only."""

    def get(self, run_id: RunId) -> GenerationRun:
        """Return the run identified by ``run_id``. Raises if absent."""

    def latest(self) -> GenerationRun | None:
        """Return the most recently appended run, or ``None`` if empty."""
