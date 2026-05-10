"""In-memory ``RunRepository`` adapter.

A trivial dict-backed store satisfying the
:class:`~ai_platform_generator.ports.RunRepository` port. Useful in
unit / integration tests; production wiring uses the future
``JsonlRunRepository`` adapter (see
``docs/ddd/04-tactical-design.md`` §6.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import GenerationRun
    from ai_platform_generator.domain.values import RunId


class InMemoryRunRepository:
    """A trivial dict-backed :class:`RunRepository` for tests + composition."""

    def __init__(self) -> None:
        # Keyed by ``RunId`` (or any hashable identity) → run aggregate.
        self._store: dict[Any, GenerationRun] = {}
        # Insertion order for ``latest()`` so tests don't depend on dict
        # iteration semantics across Python versions.
        self._order: list[Any] = []

    # ------------------------------------------------------------------
    # RunRepository protocol
    # ------------------------------------------------------------------
    def append(self, run: GenerationRun) -> None:
        """Persist ``run``. Idempotent: re-appending the same id is a no-op."""
        rid = self._key(run)
        if rid not in self._store:
            self._order.append(rid)
        self._store[rid] = run

    def get(self, run_id: RunId) -> GenerationRun:
        """Return the run identified by ``run_id``; raises :class:`KeyError`."""
        try:
            return self._store[run_id]
        except KeyError as exc:
            raise KeyError(f"No run stored for run_id={run_id!r}") from exc

    def latest(self) -> GenerationRun | None:
        """Return the most recently appended run, or ``None`` if empty."""
        if not self._order:
            return None
        return self._store[self._order[-1]]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _key(run: GenerationRun) -> Any:
        """Extract a hashable identity from ``run``.

        Falls back to ``id(run)`` if the aggregate has no ``id`` attr —
        useful while Agent E's ``GenerationRun`` aggregate is in flight.
        """
        return getattr(run, "id", id(run))

    # ----- test-only sugar ---------------------------------------------
    def __len__(self) -> int:
        return len(self._store)

    def all(self) -> list[GenerationRun]:
        """Return every stored run, in insertion order."""
        return [self._store[k] for k in self._order]
