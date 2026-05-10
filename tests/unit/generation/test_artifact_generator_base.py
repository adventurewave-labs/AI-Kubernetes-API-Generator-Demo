"""Tests for :class:`ArtifactGenerator` (Template Method base class)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.generation.artifact_generator import (
    DEFAULT_FILE_MODE,
    ArtifactGenerator,
    _clear_registry_for_tests,
    get_registered_generators,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile


# ---------------------------------------------------------------------------
# Fixture: a tiny concrete subclass that records the order of hook calls.
# ---------------------------------------------------------------------------
class _RecordingGenerator(ArtifactGenerator):
    name = "recorder"
    artefact_type = ArtifactType.OPENAPI

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.target: Path | None = None

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        self.calls.append("preconditions")

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        self.calls.append("plan")
        self.target = target
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "openapi.json", target / "extras.txt"),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        self.calls.append("render")
        return (
            _RenderedFile(path=plan.target_files[0], payload=b'{"k":"v"}'),
            _RenderedFile(path=plan.target_files[1], payload=b"hello\n"),
        )

    def _post_process(
        self, files: tuple[_RenderedFile, ...]
    ) -> tuple[_RenderedFile, ...]:
        self.calls.append("post_process")
        return files


# ---------------------------------------------------------------------------
# Lifecycle order
# ---------------------------------------------------------------------------
def test_generate_runs_hooks_in_correct_order(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)

    assert gen.calls == ["preconditions", "plan", "render", "post_process"]
    assert len(artefacts) == 2


def test_generate_target_must_be_path(sample_ir: OpenAPIDocument) -> None:
    gen = _RecordingGenerator()
    with pytest.raises(TypeError, match="target must be a Path"):
        gen.generate(sample_ir, "/tmp")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Finalisation: checksums + mode + artefact_type
# ---------------------------------------------------------------------------
def test_finalise_sets_default_mode_on_every_artefact(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)
    assert all(a.mode == DEFAULT_FILE_MODE for a in artefacts)
    assert DEFAULT_FILE_MODE == 0o644  # documents the contract


def test_finalise_tags_every_artefact_with_generator_type(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)
    assert all(a.artefact_type == ArtifactType.OPENAPI for a in artefacts)


def test_finalise_relativises_absolute_paths_under_target(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    """``RenderedArtifact.path`` must be relative — the base class strips
    the per-run ``target`` prefix that ``_plan`` / ``_render`` use."""
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)
    for a in artefacts:
        assert not a.path.is_absolute()
    paths = {a.path.as_posix() for a in artefacts}
    assert paths == {"openapi.json", "extras.txt"}


def test_finalise_computes_correct_sha256_per_file(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)

    expected = {
        a.path: hashlib.sha256(a.payload).hexdigest() for a in artefacts
    }
    for art in artefacts:
        assert art.checksum.algorithm == "sha256"
        assert art.checksum.value == expected[art.path]
        assert art.checksum.matches(art.payload)


def test_finalise_preserves_payload_bytes(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _RecordingGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)
    payloads = {a.path.as_posix(): a.payload for a in artefacts}
    assert payloads["openapi.json"] == b'{"k":"v"}'
    assert payloads["extras.txt"] == b"hello\n"


# ---------------------------------------------------------------------------
# Default ``_post_process`` is a no-op
# ---------------------------------------------------------------------------
class _NoPostProcessGenerator(ArtifactGenerator):
    name = "noop-pp"
    artefact_type = ArtifactType.OPENAPI

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "f.txt",),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        return (_RenderedFile(path=plan.target_files[0], payload=b"x"),)


def test_default_post_process_is_identity(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _NoPostProcessGenerator()
    artefacts = gen.generate(sample_ir, tmp_path)
    assert len(artefacts) == 1
    assert artefacts[0].payload == b"x"


# ---------------------------------------------------------------------------
# Render-result type guards
# ---------------------------------------------------------------------------
class _BadRenderGenerator(ArtifactGenerator):
    name = "bad-render"
    artefact_type = ArtifactType.OPENAPI

    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        pass

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / "f.txt",),
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        return [object()]  # type: ignore[return-value]


def test_finalise_rejects_non_tuple_render_output(
    tmp_path: Path, sample_ir: OpenAPIDocument
) -> None:
    gen = _BadRenderGenerator()
    with pytest.raises(TypeError, match="must return a tuple"):
        gen.generate(sample_ir, tmp_path)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_register_generator_adds_to_registry() -> None:
    _clear_registry_for_tests()

    @register_generator
    class _G(ArtifactGenerator):
        name = "demo"
        artefact_type = ArtifactType.OPENAPI

        def _check_preconditions(self, ir: OpenAPIDocument) -> None:
            pass

        def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
            return GenerationPlan(
                generator_name=self.name,
                artefact_type=self.artefact_type,
                target_files=(),
            )

        def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
            return ()

    try:
        registry = get_registered_generators()
        assert "demo" in registry
        assert registry["demo"] is _G
        # Returned dict is a copy — mutating it must not corrupt the registry.
        registry["other"] = _G
        assert "other" not in get_registered_generators()
    finally:
        _clear_registry_for_tests()


def test_register_generator_rejects_blank_name() -> None:
    _clear_registry_for_tests()

    class _G(ArtifactGenerator):
        name = ""  # invalid
        artefact_type = ArtifactType.OPENAPI

        def _check_preconditions(self, ir: OpenAPIDocument) -> None:
            pass

        def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
            return GenerationPlan(
                generator_name="x",
                artefact_type=self.artefact_type,
                target_files=(),
            )

        def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
            return ()

    with pytest.raises(ValueError, match="must be a non-empty str"):
        register_generator(_G)


def test_register_generator_rejects_duplicate_name() -> None:
    _clear_registry_for_tests()

    class _Base(ArtifactGenerator):
        name = "dup"
        artefact_type = ArtifactType.OPENAPI

        def _check_preconditions(self, ir: OpenAPIDocument) -> None:
            pass

        def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
            return GenerationPlan(
                generator_name=self.name,
                artefact_type=self.artefact_type,
                target_files=(),
            )

        def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
            return ()

    class _A(_Base):
        pass

    class _B(_Base):
        pass

    register_generator(_A)
    try:
        with pytest.raises(ValueError, match="already registered"):
            register_generator(_B)
    finally:
        _clear_registry_for_tests()


def test_register_generator_idempotent_for_same_class() -> None:
    _clear_registry_for_tests()

    class _G(ArtifactGenerator):
        name = "again"
        artefact_type = ArtifactType.OPENAPI

        def _check_preconditions(self, ir: OpenAPIDocument) -> None:
            pass

        def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
            return GenerationPlan(
                generator_name=self.name,
                artefact_type=self.artefact_type,
                target_files=(),
            )

        def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
            return ()

    register_generator(_G)
    # Second call with the *same* class is a no-op, not an error.
    register_generator(_G)
    assert get_registered_generators()["again"] is _G
    _clear_registry_for_tests()


def test_register_generator_rejects_non_class() -> None:
    with pytest.raises(TypeError, match="ArtifactGenerator subclass"):
        register_generator("not-a-class")  # type: ignore[arg-type]
