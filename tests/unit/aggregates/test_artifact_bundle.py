"""Tests for ``ArtifactBundle`` aggregate root and friends."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp
from uuid import UUID, uuid4

import pytest

from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactBundle,
    ArtifactRef,
    ArtifactType,
    InvalidArtifactBundle,
    InvalidProvenanceManifest,
    ProvenanceManifest,
    RenderedArtifact,
    make_artifact_refs,
)
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import ChecksumMismatch
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


def _request() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        spec_properties=(
            SpecProperty(
                name="x",
                type=PropertyType.STRING,
                description="d",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="d",
        provider_mode=ProviderMode.LIVE,
    )


def _artifact(
    path: str = "openapi.json", payload: bytes = b"{}", at: ArtifactType = ArtifactType.OPENAPI
) -> RenderedArtifact:
    return RenderedArtifact(
        path=Path(path),
        payload=payload,
        mode=0o644,
        artefact_type=at,
        checksum=Checksum.of(payload),
    )


def _manifest(run_id: RunId, refs: tuple[ArtifactRef, ...]) -> ProvenanceManifest:
    return ProvenanceManifest(
        run_id=run_id,
        tool_version="0.1.0",
        git_sha="abc123",
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        request=_request(),
        provider_mode=ProviderMode.LIVE,
        model_id=None,
        files=refs,
    )


# ---------------------------------------------------------------------------
# RenderedArtifact
# ---------------------------------------------------------------------------


def test_rendered_artifact_happy_path() -> None:
    a = _artifact()
    assert a.path == Path("openapi.json")
    assert a.payload == b"{}"


def test_rendered_artifact_accepts_absolute_path() -> None:
    # Absolute paths are accepted at the artefact level; the bundle
    # decides whether the path is reachable from its target_dir.
    a = RenderedArtifact(
        path=Path("/tmp/openapi.json"),
        payload=b"x",
        mode=0o644,
        artefact_type=ArtifactType.OPENAPI,
        checksum=Checksum.of(b"x"),
    )
    assert a.path == Path("/tmp/openapi.json")


def test_rendered_artifact_rejects_traversal() -> None:
    with pytest.raises(InvalidArtifactBundle):
        RenderedArtifact(
            path=Path("../escape.txt"),
            payload=b"x",
            mode=0o644,
            artefact_type=ArtifactType.OPENAPI,
            checksum=Checksum.of(b"x"),
        )


def test_rendered_artifact_rejects_checksum_mismatch() -> None:
    with pytest.raises(ChecksumMismatch):
        RenderedArtifact(
            path=Path("openapi.json"),
            payload=b"x",
            mode=0o644,
            artefact_type=ArtifactType.OPENAPI,
            checksum=Checksum.of(b"y"),
        )


def test_rendered_artifact_rejects_bad_mode() -> None:
    with pytest.raises(InvalidArtifactBundle):
        RenderedArtifact(
            path=Path("x"),
            payload=b"x",
            mode=-1,
            artefact_type=ArtifactType.OPENAPI,
            checksum=Checksum.of(b"x"),
        )


# ---------------------------------------------------------------------------
# ProvenanceManifest
# ---------------------------------------------------------------------------


def test_provenance_manifest_happy_path() -> None:
    rid = RunId.new()
    m = _manifest(rid, ())
    assert m.run_id == rid
    assert m.file_paths() == ()


def test_provenance_manifest_rejects_blank_tool_version() -> None:
    with pytest.raises(InvalidProvenanceManifest):
        ProvenanceManifest(
            run_id=RunId.new(),
            tool_version="   ",
            git_sha="sha",
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            request=_request(),
            provider_mode=ProviderMode.LIVE,
            model_id=None,
            files=(),
        )


# ---------------------------------------------------------------------------
# ArtifactBundle
# ---------------------------------------------------------------------------


def test_bundle_happy_path() -> None:
    rid = RunId.new()
    a1 = _artifact(path="openapi.json", payload=b"{}")
    a2 = _artifact(path="crd.yaml", payload=b"apiVersion: v1\n", at=ArtifactType.CRD)
    refs = make_artifact_refs((a1, a2))
    bundle = ArtifactBundle(
        run_id=rid,
        target_dir=Path(mkdtemp()),
        files=(a1, a2),
        manifest=_manifest(rid, refs),
    )
    assert bundle.by_path(Path("openapi.json")) == a1
    assert bundle.of_type(ArtifactType.CRD) == (a2,)


def test_bundle_rejects_relative_target_dir() -> None:
    rid = RunId.new()
    with pytest.raises(InvalidArtifactBundle):
        ArtifactBundle(
            run_id=rid,
            target_dir=Path("relative/dir"),
            files=(),
            manifest=_manifest(rid, ()),
        )


def test_bundle_rejects_duplicate_paths() -> None:
    rid = RunId.new()
    a1 = _artifact(path="x.json", payload=b"a")
    a2 = _artifact(path="x.json", payload=b"b")
    refs = make_artifact_refs((a1, a2))
    with pytest.raises(InvalidArtifactBundle):
        ArtifactBundle(
            run_id=rid,
            target_dir=Path(mkdtemp()),
            files=(a1, a2),
            manifest=_manifest(rid, refs),
        )


def test_bundle_rejects_manifest_run_id_mismatch() -> None:
    rid_a = RunId.new()
    rid_b = RunId.new()
    a1 = _artifact()
    refs = make_artifact_refs((a1,))
    with pytest.raises(InvalidArtifactBundle):
        ArtifactBundle(
            run_id=rid_a,
            target_dir=Path(mkdtemp()),
            files=(a1,),
            manifest=_manifest(rid_b, refs),
        )


def test_bundle_rejects_manifest_file_mismatch() -> None:
    rid = RunId.new()
    a1 = _artifact(path="a.json", payload=b"a")
    a2 = _artifact(path="b.json", payload=b"b")
    # Manifest references a1 but bundle contains a2.
    with pytest.raises(InvalidArtifactBundle):
        ArtifactBundle(
            run_id=rid,
            target_dir=Path(mkdtemp()),
            files=(a2,),
            manifest=_manifest(rid, make_artifact_refs((a1,))),
        )


def test_make_artifact_refs_pairs_path_and_checksum() -> None:
    a1 = _artifact(path="a.json", payload=b"a")
    a2 = _artifact(path="b.json", payload=b"b", at=ArtifactType.CRD)
    refs = make_artifact_refs((a1, a2))
    assert refs == (
        ArtifactRef(path=Path("a.json"), checksum=Checksum.of(b"a")),
        ArtifactRef(path=Path("b.json"), checksum=Checksum.of(b"b")),
    )


def test_artifact_type_members_present() -> None:
    # Spot-check the StrEnum members.
    assert ArtifactType.OPENAPI.value == "openapi"
    assert ArtifactType.CRD.value == "crd"
    assert ArtifactType.INSTANCE.value == "instance"
    assert ArtifactType.GO_CONTROLLER.value == "go_controller"
    assert ArtifactType.MCP_SERVER.value == "mcp_server"
    assert ArtifactType.KUSTOMIZATION.value == "kustomization"


def test_uuid_used_in_test_setup_is_a_uuid() -> None:
    # Ensure imports are exercised.
    rid: UUID = uuid4()
    assert isinstance(rid, UUID)
