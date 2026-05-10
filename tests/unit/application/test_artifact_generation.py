"""Unit tests for :class:`ArtifactGenerationService`."""

from __future__ import annotations

from pathlib import Path

from ai_platform_generator.adapters.repo.in_memory import (
    InMemoryArtifactRepository,
)
from ai_platform_generator.application.services.artifact_generation import (
    ArtifactGenerationService,
)
from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactType,
    RenderedArtifact,
)
from ai_platform_generator.domain.aggregates.codegen_request import (
    CodegenRequest,
)
from ai_platform_generator.domain.aggregates.openapi_document import (
    OpenAPIDocument,
)
from ai_platform_generator.domain.values import (
    GVK,
    Checksum,
    Group,
    Kind,
    OutputPath,
    PropertyConstraints,
    PropertyType,
    ProviderMode,
    RunId,
    SpecProperty,
    Version,
)


def _rendered(rel_path: str, payload: bytes, art_type: ArtifactType) -> RenderedArtifact:
    return RenderedArtifact(
        path=Path(rel_path),
        payload=payload,
        mode=0o644,
        artefact_type=art_type,
        checksum=Checksum.of(payload),
    )


class _FakeGenerator:
    """Minimal generator that returns canned :class:`RenderedArtifact`s."""

    def __init__(self, name: str, files: list[RenderedArtifact]) -> None:
        self.name = name
        self._files = files
        self.calls = 0

    def generate(
        self, ir: OpenAPIDocument, target: Path
    ) -> list[RenderedArtifact]:
        self.calls += 1
        return list(self._files)

    def expected_paths(
        self, ir: OpenAPIDocument, target: Path
    ) -> list[Path]:
        return [f.path for f in self._files]


def _request() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(
            group=Group("platform.example.com"),
            version=Version("v1alpha1"),
            kind=Kind("Foo"),
        ),
        spec_properties=(
            SpecProperty(
                name="bar",
                type=PropertyType.STRING,
                description="something",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=Path.cwd().resolve(), relative=Path("foo")),
        description="A foo.",
        provider_mode=ProviderMode.LIVE,
    )


def _ir(req: CodegenRequest) -> OpenAPIDocument:
    return OpenAPIDocument.from_request(req)


def test_run_iterates_generators_and_emits_per_file_events(
    sink, clock, tmp_path
) -> None:
    req = _request()
    ir = _ir(req)
    crd = _rendered("foo.crd.yaml", b"crd-bytes\n", ArtifactType.CRD)
    inst = _rendered("foo.instance.yaml", b"inst-bytes\n", ArtifactType.INSTANCE)
    gen = _FakeGenerator("crd-and-instance", [crd, inst])
    svc = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=sink,
        clock=clock,
        generators=[gen],
    )

    bundle = svc.run(
        ir,
        request=req,
        target_dir=tmp_path,
        run_id=RunId.new(),
    )

    assert gen.calls == 1
    assert bundle.target_dir == tmp_path
    assert len(bundle.files) == 2
    sink.assert_events_in_order(
        "GenerationPlanned",
        "ArtifactGenerated",
        "ArtifactGenerated",
        "ArtifactBundleSealed",
    )


def test_run_persists_through_repository(sink, clock, tmp_path) -> None:
    repo = InMemoryArtifactRepository()
    req = _request()
    ir = _ir(req)
    rid = RunId.new()
    svc = ArtifactGenerationService(
        repo=repo, events=sink, clock=clock, generators=[]
    )

    bundle = svc.run(ir, request=req, target_dir=tmp_path, run_id=rid)

    assert repo.exists(rid)
    assert repo.load(rid) is bundle


def test_run_works_with_no_generators(sink, clock, tmp_path) -> None:
    """No generators → no per-file events but the bundle is still sealed."""
    req = _request()
    ir = _ir(req)
    svc = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=sink,
        clock=clock,
        generators=[],
    )

    bundle = svc.run(ir, request=req, target_dir=tmp_path, run_id=RunId.new())
    assert len(bundle.files) == 0
    assert sink.events_with_name("ArtifactBundleSealed")


def test_manifest_carries_tool_version_and_request(sink, clock, tmp_path) -> None:
    from ai_platform_generator import __version__ as tool_version

    req = _request()
    ir = _ir(req)
    svc = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=sink,
        clock=clock,
        generators=[],
    )
    bundle = svc.run(ir, request=req, target_dir=tmp_path, run_id=RunId.new())

    manifest = bundle.manifest
    assert manifest.tool_version == tool_version
    assert manifest.request is req
    assert manifest.provider_mode is ProviderMode.LIVE
    assert manifest.git_sha  # something — possibly "unknown"
