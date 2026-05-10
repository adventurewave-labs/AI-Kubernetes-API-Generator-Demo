"""``ArtifactPlanner`` — drives generators' ``_plan`` step + collision check.

Per ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §5 step 2,
the application service must validate plans before any rendering — two
generators writing to the same path is a programming bug, not a runtime
failure mode. The planner runs each requested generator's ``_plan``,
collects the resulting :class:`GenerationPlan` tuple, and raises a
domain-typed error if any path collides between plans.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from ai_platform_generator.domain.errors.artifact import ArtifactGenerationError
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        ArtifactType,
        OpenAPIDocument,
    )
    from ai_platform_generator.domain.generation.artifact_generator import (
        ArtifactGenerator,
    )


class PathCollision(ArtifactGenerationError):
    """Two generators planned to write the same file.

    Programmer error — terminal. The exception message names both
    offending generators and the path so the bug is trivial to locate.
    """

    code = "E_ARTIFACT_PATH_COLLISION"


class ArtifactPlanner:
    """Drives the per-generator planning step and validates the result.

    The planner is *stateless* — it accepts a mapping of available
    generators (so the caller controls instantiation order, DI of the
    :class:`ChecksumService`, etc.) and produces a deterministic tuple
    of :class:`GenerationPlan` instances.
    """

    def __init__(
        self,
        generators: Mapping[str, ArtifactGenerator],
    ) -> None:
        # Lazy import: avoid a circular ``services -> generation -> services``
        # at module-load time.
        from ai_platform_generator.domain.generation.artifact_generator import (
            ArtifactGenerator as _ArtifactGenerator,
        )

        if not isinstance(generators, Mapping):
            raise TypeError(
                f"generators must be a Mapping, got {type(generators).__name__}"
            )
        for key, gen in generators.items():
            if not isinstance(gen, _ArtifactGenerator):
                raise TypeError(
                    f"generators[{key!r}] must be an ArtifactGenerator, got "
                    f"{type(gen).__name__}"
                )
        # Defensive copy so the caller cannot mutate our view post hoc.
        self._generators: dict[str, ArtifactGenerator] = dict(generators)

    def plan(
        self,
        ir: OpenAPIDocument,
        target: Path,
        requested_types: Iterable[ArtifactType],
    ) -> tuple[GenerationPlan, ...]:
        """Build a plan for every requested artefact type.

        Parameters
        ----------
        ir:
            The validated OpenAPI IR (Agent E's aggregate; typed loosely
            for forward-reference safety).
        target:
            The output directory the bundle will be written to.
        requested_types:
            The artefact types to plan. Each must match the
            :attr:`ArtifactGenerator.artefact_type` of exactly one
            generator in :attr:`_generators`.

        Returns
        -------
        tuple[GenerationPlan, ...]
            Plans in the iteration order of ``requested_types``.

        Raises
        ------
        ArtifactGenerationError
            If a requested type has no matching generator.
        PathCollision
            If two plans want to write the same path.
        """
        if not isinstance(target, Path):
            raise TypeError(
                f"target must be a Path, got {type(target).__name__}"
            )

        # Index generators by their artefact_type for O(1) lookup. We
        # rebuild this every call (rather than caching at construction)
        # so a generator added to the mapping at runtime is picked up.
        by_type: dict[ArtifactType, ArtifactGenerator] = {}
        for gen in self._generators.values():
            atype = getattr(gen, "artefact_type", None)
            if atype is None:
                raise ArtifactGenerationError(
                    f"generator {gen.name!r} has no artefact_type set"
                )
            if atype in by_type:
                raise ArtifactGenerationError(
                    f"two generators claim artefact_type {atype!r}: "
                    f"{by_type[atype].name!r} and {gen.name!r}"
                )
            by_type[atype] = gen

        plans: list[GenerationPlan] = []
        for atype in requested_types:
            try:
                gen = by_type[atype]
            except KeyError as exc:
                raise ArtifactGenerationError(
                    f"no generator registered for artefact_type {atype!r}"
                ) from exc
            plan = gen._plan(ir, target)
            if not isinstance(plan, GenerationPlan):
                raise ArtifactGenerationError(
                    f"generator {gen.name!r}._plan must return a "
                    f"GenerationPlan, got {type(plan).__name__}"
                )
            plans.append(plan)

        self._assert_no_collisions(plans)
        return tuple(plans)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _assert_no_collisions(plans: list[GenerationPlan]) -> None:
        """Raise :class:`PathCollision` if any two plans share a path."""
        seen: dict[Path, str] = {}
        for plan in plans:
            for path in plan.target_files:
                prior = seen.get(path)
                if prior is not None and prior != plan.generator_name:
                    raise PathCollision(
                        f"path collision on {path}: generators "
                        f"{prior!r} and {plan.generator_name!r} both want it"
                    )
                seen[path] = plan.generator_name
