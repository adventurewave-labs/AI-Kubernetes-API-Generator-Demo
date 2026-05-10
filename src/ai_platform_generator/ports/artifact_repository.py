"""``ArtifactRepository`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_platform_generator.domain.aggregates import ArtifactBundle
    from ai_platform_generator.domain.values import RunId


@runtime_checkable
class ArtifactRepository(Protocol):
    """Persist and retrieve :class:`ArtifactBundle` aggregates."""

    def save(self, bundle: ArtifactBundle) -> None:
        """Persist the bundle. Idempotent on ``bundle.run_id``."""

    def load(self, run_id: RunId) -> ArtifactBundle:
        """Return the bundle previously saved under ``run_id``."""

    def exists(self, run_id: RunId) -> bool:
        """Return ``True`` iff a bundle is stored under ``run_id``."""
