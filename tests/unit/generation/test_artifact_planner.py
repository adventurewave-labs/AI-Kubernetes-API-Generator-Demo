"""Tests for :class:`ArtifactPlanner` — collision detection across plans."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors.artifact import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile
from ai_platform_generator.domain.services.artifact_planner import (
    ArtifactPlanner,
    PathCollision,
)


# ---------------------------------------------------------------------------
# Fixture generators — minimal subclasses that produce predictable plans.
# ---------------------------------------------------------------------------
class _StubGenerator(ArtifactGenerator):
    """A do-nothing generator with a configurable plan."""

    def __init__(
        self,
        *,
        name: str,
        artefact_type: ArtifactType,
        files: tuple[Path, ...],
    ) -> None:
        super().__init__()
        self.name = name
        self.artefact_type = artefact_type
        self._files = files

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        return None

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=tuple(target / f for f in self._files),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        return tuple(
            _RenderedFile(path=p, payload=b"x") for p in plan.target_files
        )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def test_planner_rejects_non_mapping() -> None:
    with pytest.raises(TypeError, match="generators must be a Mapping"):
        ArtifactPlanner([])  # type: ignore[arg-type]


def test_planner_rejects_non_generator_value() -> None:
    with pytest.raises(TypeError, match="must be an ArtifactGenerator"):
        ArtifactPlanner({"crd": object()})  # type: ignore[dict-item]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_planner_returns_plan_per_requested_type(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    crd = _StubGenerator(
        name="crd",
        artefact_type=ArtifactType.CRD,
        files=(Path("postgres.crd.yaml"),),
    )
    inst = _StubGenerator(
        name="instance",
        artefact_type=ArtifactType.INSTANCE,
        files=(Path("postgres.instance.yaml"),),
    )
    planner = ArtifactPlanner({"crd": crd, "instance": inst})

    plans = planner.plan(
        ir=sample_ir,
        target=tmp_path,
        requested_types=(ArtifactType.CRD, ArtifactType.INSTANCE),
    )

    assert len(plans) == 2
    assert plans[0].generator_name == "crd"
    assert plans[1].generator_name == "instance"
    assert plans[0].target_files == (tmp_path / "postgres.crd.yaml",)


def test_planner_preserves_request_order(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    crd = _StubGenerator(
        name="crd", artefact_type=ArtifactType.CRD, files=(Path("a.yaml"),)
    )
    inst = _StubGenerator(
        name="inst", artefact_type=ArtifactType.INSTANCE, files=(Path("b.yaml"),)
    )
    planner = ArtifactPlanner({"crd": crd, "inst": inst})

    plans = planner.plan(
        ir=sample_ir,
        target=tmp_path,
        requested_types=(ArtifactType.INSTANCE, ArtifactType.CRD),
    )
    assert [p.generator_name for p in plans] == ["inst", "crd"]


# ---------------------------------------------------------------------------
# Collision detection (the core invariant)
# ---------------------------------------------------------------------------
def test_planner_detects_path_collision_across_generators(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    a = _StubGenerator(
        name="a", artefact_type=ArtifactType.CRD, files=(Path("shared.yaml"),)
    )
    b = _StubGenerator(
        name="b", artefact_type=ArtifactType.INSTANCE, files=(Path("shared.yaml"),)
    )
    planner = ArtifactPlanner({"a": a, "b": b})
    with pytest.raises(PathCollision) as exc_info:
        planner.plan(
            ir=sample_ir,
            target=tmp_path,
            requested_types=(ArtifactType.CRD, ArtifactType.INSTANCE),
        )
    assert "shared.yaml" in str(exc_info.value)
    assert "'a'" in str(exc_info.value)
    assert "'b'" in str(exc_info.value)


def test_planner_does_not_flag_same_generator_paths(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    """A generator that lists the same path twice in its own plan is its own
    problem — the planner only detects *cross*-generator collisions."""
    a = _StubGenerator(
        name="a",
        artefact_type=ArtifactType.CRD,
        files=(Path("x.yaml"), Path("y.yaml")),
    )
    planner = ArtifactPlanner({"a": a})
    plans = planner.plan(
        ir=sample_ir,
        target=tmp_path,
        requested_types=(ArtifactType.CRD,),
    )
    assert len(plans) == 1


# ---------------------------------------------------------------------------
# Misconfiguration
# ---------------------------------------------------------------------------
def test_planner_raises_when_no_generator_for_type(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    crd = _StubGenerator(
        name="crd", artefact_type=ArtifactType.CRD, files=(Path("a.yaml"),)
    )
    planner = ArtifactPlanner({"crd": crd})
    with pytest.raises(ArtifactGenerationError, match="no generator registered"):
        planner.plan(
            ir=sample_ir,
            target=tmp_path,
            requested_types=(ArtifactType.GO_CONTROLLER,),
        )


def test_planner_raises_when_two_generators_share_artefact_type(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    a = _StubGenerator(
        name="a", artefact_type=ArtifactType.CRD, files=(Path("x.yaml"),)
    )
    b = _StubGenerator(
        name="b", artefact_type=ArtifactType.CRD, files=(Path("y.yaml"),)
    )
    planner = ArtifactPlanner({"a": a, "b": b})
    with pytest.raises(
        ArtifactGenerationError, match="two generators claim artefact_type"
    ):
        planner.plan(
            ir=sample_ir,
            target=tmp_path,
            requested_types=(ArtifactType.CRD,),
        )


def test_planner_target_must_be_path(sample_ir: OpenAPIDocument) -> None:
    crd = _StubGenerator(
        name="crd", artefact_type=ArtifactType.CRD, files=(Path("x.yaml"),)
    )
    planner = ArtifactPlanner({"crd": crd})
    with pytest.raises(TypeError, match="target must be a Path"):
        planner.plan(
            ir=sample_ir,
            target="not-a-path",  # type: ignore[arg-type]
            requested_types=(ArtifactType.CRD,),
        )
