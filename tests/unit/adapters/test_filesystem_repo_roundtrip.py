"""save → load round-trip tests for :class:`FilesystemArtifactRepository`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

import pytest

from ai_platform_generator.adapters.repo.filesystem import (
    FilesystemArtifactRepository,
)
from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactBundle,
    ArtifactType,
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
                name="size",
                type=PropertyType.INTEGER,
                description="size in GiB",
                constraints=PropertyConstraints(minimum=1, maximum=4096),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="round-trip fixture",
        provider_mode=ProviderMode.LIVE,
    )


def _artifact(
    path: str, payload: bytes, kind: ArtifactType = ArtifactType.OPENAPI
) -> RenderedArtifact:
    return RenderedArtifact(
        path=Path(path),
        payload=payload,
        mode=0o644,
        artefact_type=kind,
        checksum=Checksum.of(payload),
    )


def _bundle(target_dir: Path, run_id: RunId | None = None) -> ArtifactBundle:
    rid = run_id or RunId.new()
    a1 = _artifact("openapi.json", b'{"openapi":"3.0.0"}', ArtifactType.OPENAPI)
    a2 = _artifact("database.crd.yaml", b"kind: CustomResourceDefinition\n", ArtifactType.CRD)
    a3 = _artifact(
        "database.instance.yaml", b"kind: Database\n", ArtifactType.INSTANCE
    )
    refs = make_artifact_refs((a1, a2, a3))
    manifest = ProvenanceManifest(
        run_id=rid,
        tool_version="0.1.0",
        git_sha="cafef00d",
        generated_at=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
        request=_request(),
        provider_mode=ProviderMode.LIVE,
        model_id="test-model",
        files=refs,
    )
    return ArtifactBundle(
        run_id=rid,
        target_dir=target_dir,
        files=(a1, a2, a3),
        manifest=manifest,
    )


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    target = root / "run-1"
    bundle = _bundle(target.resolve())

    repo.save(bundle)
    reloaded = repo.load(bundle.run_id)

    # Bundle identity preserved by run_id and bytes-on-disk → checksums.
    assert reloaded.run_id == bundle.run_id
    assert {a.path for a in reloaded.files} == {a.path for a in bundle.files}
    for art in bundle.files:
        on_disk = reloaded.by_path(art.path)
        assert on_disk is not None
        assert on_disk.payload == art.payload
        assert on_disk.checksum == art.checksum


def test_exists_finds_run(tmp_path: Path) -> None:
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    bundle = _bundle((root / "run-1").resolve())
    repo.save(bundle)
    assert repo.exists(bundle.run_id) is True


def test_exists_false_for_missing_run(tmp_path: Path) -> None:
    repo = FilesystemArtifactRepository(tmp_path / "store")
    assert repo.exists(RunId.new()) is False


def test_load_missing_raises_key_error(tmp_path: Path) -> None:
    repo = FilesystemArtifactRepository(tmp_path / "store")
    with pytest.raises(KeyError):
        repo.load(RunId.new())


def test_save_writes_files_with_expected_modes(tmp_path: Path) -> None:
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    target = root / "run-1"
    bundle = _bundle(target.resolve())
    repo.save(bundle)

    manifest_path = target / "manifest.json"
    assert manifest_path.is_file()
    # 0o600 for manifest
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    # 0o644 for normal artefacts
    openapi_path = target / "openapi.json"
    assert openapi_path.stat().st_mode & 0o777 == 0o644


def test_save_detects_disk_checksum_mismatch(tmp_path: Path, monkeypatch) -> None:
    """If something writes garbage to disk we get :class:`ChecksumMismatch`."""
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    target = root / "run-1"
    bundle = _bundle(target.resolve())

    real_replace = __import__("os").replace

    def _replace_with_corruption(src, dst) -> None:  # type: ignore[no-untyped-def]
        real_replace(src, dst)
        # Tamper with on-disk content for a non-manifest artefact only,
        # before the post-write checksum check runs.
        if str(dst).endswith("openapi.json"):
            Path(str(dst)).write_bytes(b"corrupted")

    monkeypatch.setattr("ai_platform_generator.adapters.repo.filesystem.os.replace",
                        _replace_with_corruption)

    with pytest.raises(ChecksumMismatch):
        repo.save(bundle)
