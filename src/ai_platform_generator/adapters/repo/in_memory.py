"""In-memory ``ArtifactRepository`` for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 3.2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_platform_generator.domain.aggregates import ArtifactBundle
    from ai_platform_generator.domain.values import RunId


class InMemoryArtifactRepository:
    """Trivial dict-backed implementation of :class:`ArtifactRepository`."""

    def __init__(self) -> None:
        # The eventual ``RunId`` is a UUID-shaped value object; a plain
        # dict suffices regardless of its concrete type.
        self._store: dict[Any, ArtifactBundle] = {}

    def save(self, bundle: ArtifactBundle) -> None:
        self._store[bundle.run_id] = bundle

    def load(self, run_id: RunId) -> ArtifactBundle:
        try:
            return self._store[run_id]
        except KeyError as exc:
            raise KeyError(f"No bundle stored for run_id={run_id!r}") from exc

    def exists(self, run_id: RunId) -> bool:
        return run_id in self._store

    # ----- test-only sugar ---------------------------------------------

    def __len__(self) -> int:
        return len(self._store)
