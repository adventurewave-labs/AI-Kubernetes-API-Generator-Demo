"""Path-safety tests for :class:`FilesystemArtifactRepository`.

Per ADR-0020 §3 and ``docs/ddd/07-anti-corruption-layers.md`` §3.3
the filesystem adapter must reject:

* paths that escape the configured root via ``..``;
* artefacts written under an absolute path outside the bundle's
  ``target_dir``;
* symlinks pointing outside the configured root.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

import pytest

from ai_platform_generator.adapters.repo.filesystem import (
    FilesystemArtifactRepository,
    _safe_resolve,
)
from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactBundle,
    ArtifactType,
    ProvenanceManifest,
    RenderedArtifact,
    make_artifact_refs,
)
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import ArtifactWriteFailed
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


def _artifact(path: str, payload: bytes = b"x") -> RenderedArtifact:
    return RenderedArtifact(
        path=Path(path),
        payload=payload,
        mode=0o644,
        artefact_type=ArtifactType.OPENAPI,
        checksum=Checksum.of(payload),
    )


def _bundle(target_dir: Path, *artefacts: RenderedArtifact) -> ArtifactBundle:
    rid = RunId.new()
    refs = make_artifact_refs(artefacts)
    manifest = ProvenanceManifest(
        run_id=rid,
        tool_version="0.1.0",
        git_sha="deadbeef",
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        request=_request(),
        provider_mode=ProviderMode.LIVE,
        model_id=None,
        files=refs,
    )
    return ArtifactBundle(
        run_id=rid,
        target_dir=target_dir,
        files=tuple(artefacts),
        manifest=manifest,
    )


def test_safe_resolve_accepts_path_inside_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    inside = _safe_resolve(root, Path("a/b.txt"))
    assert inside == (root / "a/b.txt").resolve()


def test_safe_resolve_rejects_dotdot(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    with pytest.raises(ArtifactWriteFailed) as excinfo:
        _safe_resolve(root, Path("../escape.txt"))
    assert excinfo.value.code == "E_ARTIFACT_PATH_TRAVERSAL"


def test_safe_resolve_rejects_absolute_outside_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    with pytest.raises(ArtifactWriteFailed) as excinfo:
        _safe_resolve(root, Path("/etc/passwd"))
    assert excinfo.value.code == "E_ARTIFACT_PATH_TRAVERSAL"


def test_save_rejects_target_dir_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "store"
    other = tmp_path / "elsewhere"
    other.mkdir(parents=True)
    repo = FilesystemArtifactRepository(root)
    bundle = _bundle(other.resolve(), _artifact("openapi.json"))
    with pytest.raises(ArtifactWriteFailed) as excinfo:
        repo.save(bundle)
    assert excinfo.value.code == "E_ARTIFACT_PATH_TRAVERSAL"


def test_save_rejects_artifact_with_dotdot(tmp_path: Path) -> None:
    root = tmp_path / "store"
    target = root / "run-1"
    repo = FilesystemArtifactRepository(root)
    # Construct a payload artefact with a benign path; the bundle's
    # invariants forbid '..' in RenderedArtifact directly. So we mimic
    # the threat by writing a bundle whose target_dir is fine but whose
    # artefact path is absolute and points outside.
    artefact_outside = RenderedArtifact(
        path=Path("/tmp/escape.txt"),
        payload=b"x",
        mode=0o644,
        artefact_type=ArtifactType.OPENAPI,
        checksum=Checksum.of(b"x"),
    )
    bundle = _bundle(target.resolve(), artefact_outside)
    with pytest.raises(ArtifactWriteFailed) as excinfo:
        repo.save(bundle)
    assert excinfo.value.code == "E_ARTIFACT_PATH_TRAVERSAL"


def test_save_rejects_symlink_target_dir_pointing_outside(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "evil"
    os.symlink(outside, link)
    repo = FilesystemArtifactRepository(root)
    # Bundle target_dir is a symlink that resolves outside root; save
    # should refuse before writing.
    bundle = _bundle(link, _artifact("openapi.json"))
    with pytest.raises(ArtifactWriteFailed) as excinfo:
        repo.save(bundle)
    assert excinfo.value.code == "E_ARTIFACT_PATH_TRAVERSAL"
