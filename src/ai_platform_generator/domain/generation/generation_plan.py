"""``GenerationPlan`` value object.

A side-effect-free description of the files an artefact generator
*would* write for a given IR + target directory. Returned by
``ArtifactGenerator._plan`` and validated for collisions by
``ArtifactPlanner`` before any rendering happens.

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §3 and §6.1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import ArtifactType


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    """Immutable plan describing what a single generator will write.

    Parameters
    ----------
    generator_name:
        Stable identifier of the generator that produced this plan
        (matches ``ArtifactGenerator.name``).
    artefact_type:
        The artefact-type tag emitted by the generator. Typed loosely as
        ``Any`` here to avoid an import cycle with the aggregates module
        (see :pep:`563` and ``TYPE_CHECKING`` import above).
    target_files:
        Absolute paths of files the generator will produce. Order is
        significant — collision detection relies on the tuple ordering
        being deterministic per generator.
    metadata:
        Generator-specific bag of context. Wrapped in a read-only
        ``MappingProxyType`` to preserve immutability.
    """

    generator_name: str
    artefact_type: ArtifactType
    target_files: tuple[Path, ...]
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.generator_name, str) or not self.generator_name:
            raise ValueError(
                f"generator_name must be a non-empty str, got {self.generator_name!r}"
            )
        if not isinstance(self.target_files, tuple):
            raise TypeError(
                f"target_files must be a tuple, got {type(self.target_files).__name__}"
            )
        for path in self.target_files:
            if not isinstance(path, Path):
                raise TypeError(
                    f"every target_files entry must be a Path, got {type(path).__name__}"
                )
        # Defensive copy: ensure metadata is read-only even if a mutable
        # mapping was passed in.
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
