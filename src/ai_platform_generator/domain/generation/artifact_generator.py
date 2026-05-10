"""Abstract :class:`ArtifactGenerator` base class (Template Method).

Implements the lifecycle described in
``docs/adr/0015-template-method-for-code-generation.md`` and
``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.1::

    generate(ir, target):
        _check_preconditions(ir)
        plan     = _plan(ir, target)
        rendered = _render(plan)              # tuple[_RenderedFile, ...]
        rendered = _post_process(rendered)
        return _finalise(rendered)            # tuple[RenderedArtifact, ...]

Concrete generators (``CrdYamlGenerator``, ``InstanceYamlGenerator``,
``GoControllerGenerator`` …) are Wave 4 work — this module only provides
the skeleton plus a registry decorator (:func:`register_generator`) so
later waves can declare their generator without the discovery code
needing to import every subclass eagerly.

Forward-reference policy
------------------------
Several types we touch (``ArtifactType``, ``RenderedArtifact``,
``OpenAPIDocument``) are owned by sibling agents (E, parallel wave) and
may not be importable at module-load time. We follow the project's
``from __future__ import annotations`` + ``TYPE_CHECKING`` convention so
this file can be imported even before Agent E lands; the only runtime
import is performed lazily inside :meth:`ArtifactGenerator._finalise`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile
from ai_platform_generator.domain.services.checksum_service import ChecksumService

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        ArtifactType,
        OpenAPIDocument,
        RenderedArtifact,
    )


# Default POSIX file mode for emitted artefacts. Overridable per-generator
# by subclassing and overriding ``_finalise``; we default to 0o644 because
# every artefact we emit today is a plain regular file.
DEFAULT_FILE_MODE = 0o644

# Module-private global registry mapping ``generator_name → class``.
# Populated via :func:`register_generator`. Application/orchestrator code
# in Wave 3+ reads this to discover the default generator set.
_generator_registry: dict[str, type[ArtifactGenerator]] = {}


class ArtifactGenerator(ABC):
    """Template Method base class for artefact generators.

    Subclasses set the class-level attributes :attr:`name` and
    :attr:`artefact_type`, then implement the three abstract hooks
    (:meth:`_check_preconditions`, :meth:`_plan`, :meth:`_render`).
    Cross-cutting policy — checksumming and ``RenderedArtifact``
    construction — lives in :meth:`_finalise` so it cannot drift between
    generators.
    """

    #: Stable, human-readable identifier of the generator (e.g. ``"crd"``).
    #: Subclasses MUST override; the empty default makes the base class
    #: instantiable only via subclassing.
    name: str = ""

    #: ``ArtifactType`` enum value tagging every file this generator
    #: emits. Subclasses MUST override (typed loosely here to avoid an
    #: import cycle with the aggregates module).
    artefact_type: ArtifactType

    def __init__(
        self, *, checksum_service: ChecksumService | None = None
    ) -> None:
        """Allow injecting a :class:`ChecksumService` for tests."""
        self._checksum_service = checksum_service or ChecksumService()

    # ------------------------------------------------------------------
    # Public Template Method
    # ------------------------------------------------------------------
    def generate(
        self, ir: OpenAPIDocument, target: Path
    ) -> tuple[RenderedArtifact, ...]:
        """Run the full lifecycle and return immutable artefacts.

        The order of calls is **fixed** — subclasses cannot reorder
        steps. They only customise individual hooks.
        """
        if not isinstance(target, Path):
            raise TypeError(f"target must be a Path, got {type(target).__name__}")

        self._check_preconditions(ir)
        plan = self._plan(ir, target)
        rendered = self._render(plan)
        rendered = self._post_process(rendered)
        return self._finalise(rendered, target)

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    @abstractmethod
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        """Validate that ``ir`` carries everything the generator needs.

        Raises an :class:`ArtifactGenerationError` subclass on failure.
        Must not mutate ``ir``.
        """

    @abstractmethod
    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        """Return a :class:`GenerationPlan` describing the work — no I/O."""

    @abstractmethod
    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        """Render every file declared in ``plan`` to bytes (no I/O)."""

    # ------------------------------------------------------------------
    # Default hooks
    # ------------------------------------------------------------------
    def _post_process(
        self, files: tuple[_RenderedFile, ...]
    ) -> tuple[_RenderedFile, ...]:
        """No-op by default — concrete generators override for gofmt/yamlfmt/etc."""
        return files

    def _finalise(
        self, files: tuple[_RenderedFile, ...], target: Path
    ) -> tuple[RenderedArtifact, ...]:
        """Wrap each ``_RenderedFile`` into an immutable ``RenderedArtifact``.

        Computes the SHA-256 checksum once per file, sets ``mode`` to
        :data:`DEFAULT_FILE_MODE`, and tags every artefact with the
        generator's :attr:`artefact_type`. The runtime import of
        ``RenderedArtifact`` is deliberately lazy so the module stays
        loadable even if Agent E's aggregates are not yet available
        (we want to be importable for tooling and unit tests of the
        renderer/planner).

        ``RenderedArtifact.path`` is required to be **relative** to
        ``target`` (per the aggregate's invariants); we relativise here
        so that subclasses can keep working with absolute paths during
        ``_plan`` / ``_render`` (which is more natural — they need to
        know the absolute write location).
        """
        # Lazy import: aggregates are owned by sibling agent E.
        from ai_platform_generator.domain.aggregates import RenderedArtifact

        if not isinstance(files, tuple):
            raise TypeError(
                f"_render/_post_process must return a tuple, got "
                f"{type(files).__name__}"
            )

        artefacts: list[RenderedArtifact] = []
        for file in files:
            if not isinstance(file, _RenderedFile):
                raise TypeError(
                    f"_render must yield _RenderedFile instances, got "
                    f"{type(file).__name__}"
                )
            checksum = self._checksum_service.sha256_of(file.payload)
            rel_path = self._relativise(file.path, target)
            artefacts.append(
                RenderedArtifact(
                    path=rel_path,
                    payload=file.payload,
                    mode=DEFAULT_FILE_MODE,
                    artefact_type=self.artefact_type,
                    checksum=checksum,
                )
            )
        return tuple(artefacts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _relativise(path: Path, target: Path) -> Path:
        """Return ``path`` relative to ``target`` if possible, else as-is.

        Most generators emit absolute paths under the target dir, in
        which case ``RenderedArtifact.path`` must be the relative form
        per the aggregate's invariants. If the caller already provided a
        relative path we honour that verbatim.
        """
        if not path.is_absolute():
            return path
        try:
            return path.relative_to(target)
        except ValueError as exc:
            raise ValueError(
                f"rendered path {path!r} is not under target {target!r}"
            ) from exc


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
def register_generator(
    cls: type[ArtifactGenerator],
) -> type[ArtifactGenerator]:
    """Class decorator that records ``cls`` in the global generator registry.

    Usage::

        @register_generator
        class CrdYamlGenerator(ArtifactGenerator):
            name = "crd"
            artefact_type = ArtifactType.CRD
            ...

    The registry is a flat ``dict[name, class]`` keyed by
    :attr:`ArtifactGenerator.name`. Re-registering a class under a name
    already in use raises :class:`ValueError` so accidental clashes fail
    loud rather than silently shadow.
    """
    if not isinstance(cls, type) or not issubclass(cls, ArtifactGenerator):
        raise TypeError(
            "register_generator expects an ArtifactGenerator subclass, "
            f"got {cls!r}"
        )
    name = getattr(cls, "name", "")
    if not isinstance(name, str) or not name:
        raise ValueError(
            f"{cls.__name__}.name must be a non-empty str to register"
        )
    if name in _generator_registry and _generator_registry[name] is not cls:
        raise ValueError(
            f"generator name {name!r} is already registered to "
            f"{_generator_registry[name].__name__}"
        )
    _generator_registry[name] = cls
    return cls


def get_registered_generators() -> dict[str, type[ArtifactGenerator]]:
    """Return a *copy* of the registry — read-only access for callers."""
    return dict(_generator_registry)


def _clear_registry_for_tests() -> None:
    """Reset the registry. **Test-only** utility — not part of the API."""
    _generator_registry.clear()
