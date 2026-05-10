"""Tests for :class:`IdempotencyVerifier`."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
class _DeterministicGenerator(ArtifactGenerator):
    """Always produces the same bytes for the same target dir."""

    name = "det"
    artefact_type = ArtifactType.OPENAPI

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "stable.yaml",),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        return (_RenderedFile(path=plan.target_files[0], payload=b"same\n"),)


class _DriftingGenerator(ArtifactGenerator):
    """Embeds a monotonically-increasing counter so each run differs."""

    name = "drifty"
    artefact_type = ArtifactType.OPENAPI

    def __init__(self) -> None:
        super().__init__()
        self._counter = itertools.count()

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "drift.yaml",),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        n = next(self._counter)
        return (
            _RenderedFile(path=plan.target_files[0], payload=f"v={n}\n".encode()),
        )


class _PartialDriftGenerator(ArtifactGenerator):
    """Stable artefact + a non-deterministic ``manifest.json`` sibling."""

    name = "partial"
    artefact_type = ArtifactType.OPENAPI

    def __init__(self) -> None:
        super().__init__()
        self._counter = itertools.count()

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "stable.yaml", target / "manifest.json"),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        n = next(self._counter)
        return (
            _RenderedFile(path=plan.target_files[0], payload=b"stable\n"),
            _RenderedFile(
                path=plan.target_files[1], payload=f"ts={n}".encode()
            ),
        )


class _ChangingShapeGenerator(ArtifactGenerator):
    """Different *file set* each run — the strongest form of drift."""

    name = "shape"
    artefact_type = ArtifactType.OPENAPI

    def __init__(self) -> None:
        super().__init__()
        self._counter = itertools.count()

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        n = next(self._counter)
        files = (target / "a.yaml",)
        if n % 2 == 1:
            files = (*files, target / "b.yaml")
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=files,
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        return tuple(
            _RenderedFile(path=p, payload=b"x") for p in plan.target_files
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_passes_when_generator_is_deterministic(
    sample_ir: OpenAPIDocument,
) -> None:
    verifier = IdempotencyVerifier()
    verifier.verify_byte_stable(_DeterministicGenerator(), sample_ir)


def test_fails_when_generator_drifts(sample_ir: OpenAPIDocument) -> None:
    verifier = IdempotencyVerifier()
    with pytest.raises(AssertionError, match="non-deterministic output"):
        verifier.verify_byte_stable(
            _DriftingGenerator(), sample_ir, runs=2,
        )


def test_ignore_paths_skips_drifting_file(sample_ir: OpenAPIDocument) -> None:
    """Drift in ``manifest.json`` is tolerated when in ``ignore_paths``."""
    verifier = IdempotencyVerifier()
    verifier.verify_byte_stable(
        _PartialDriftGenerator(),
        sample_ir,
        runs=3,
        ignore_paths=("manifest.json",),
    )


def test_ignore_paths_does_not_mask_other_drift(
    sample_ir: OpenAPIDocument,
) -> None:
    """Sanity: filtering ``manifest.json`` still surfaces drift in other files."""
    verifier = IdempotencyVerifier()
    with pytest.raises(AssertionError):
        verifier.verify_byte_stable(
            _DriftingGenerator(),
            sample_ir,
            runs=2,
            ignore_paths=("manifest.json",),  # not the drifting file
        )


def test_detects_changing_file_set(sample_ir: OpenAPIDocument) -> None:
    verifier = IdempotencyVerifier()
    with pytest.raises(AssertionError, match="different set of files"):
        verifier.verify_byte_stable(
            _ChangingShapeGenerator(), sample_ir, runs=2,
        )


def test_runs_must_be_at_least_two(sample_ir: OpenAPIDocument) -> None:
    verifier = IdempotencyVerifier()
    with pytest.raises(AssertionError, match="runs >= 2"):
        verifier.verify_byte_stable(
            _DeterministicGenerator(), sample_ir, runs=1,
        )
