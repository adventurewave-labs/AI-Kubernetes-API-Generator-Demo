"""Atomicity tests for :class:`FilesystemArtifactRepository`.

A failure mid-write must leave no partial files behind: the ``.tmp``
staging file is removed and the final file is never created.
"""

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


def _bundle(target_dir: Path) -> ArtifactBundle:
    rid = RunId.new()
    a = RenderedArtifact(
        path=Path("openapi.json"),
        payload=b'{"openapi":"3.0.0"}',
        mode=0o644,
        artefact_type=ArtifactType.OPENAPI,
        checksum=Checksum.of(b'{"openapi":"3.0.0"}'),
    )
    refs = make_artifact_refs((a,))
    manifest = ProvenanceManifest(
        run_id=rid,
        tool_version="0.1.0",
        git_sha="abc",
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        request=_request(),
        provider_mode=ProviderMode.LIVE,
        model_id=None,
        files=refs,
    )
    return ArtifactBundle(
        run_id=rid,
        target_dir=target_dir,
        files=(a,),
        manifest=manifest,
    )


def test_failed_fsync_leaves_no_partial_artefact(tmp_path: Path, monkeypatch) -> None:
    """Inject an :func:`os.fsync` failure during the artefact write.

    The ``.tmp`` staging file must be removed and the final path must
    not exist.
    """
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    target = (root / "run-1").resolve()
    bundle = _bundle(target)

    real_fsync = __import__("os").fsync

    fsync_calls = {"n": 0}

    def _flaky_fsync(fd: int) -> None:
        fsync_calls["n"] += 1
        # Fail on the very first fsync (the artefact write).
        if fsync_calls["n"] == 1:
            raise OSError("simulated fsync failure")
        real_fsync(fd)

    monkeypatch.setattr(
        "ai_platform_generator.adapters.repo.filesystem.os.fsync", _flaky_fsync
    )

    with pytest.raises(Exception):
        repo.save(bundle)

    # No partial files of any flavour.
    assert not (target / "openapi.json").exists()
    assert not (target / "openapi.json.tmp").exists()
    assert not (target / "manifest.json").exists()
    assert not (target / "manifest.json.tmp").exists()


def test_failed_replace_leaves_no_tmp_behind(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "store"
    repo = FilesystemArtifactRepository(root)
    target = (root / "run-2").resolve()
    bundle = _bundle(target)

    real_replace = __import__("os").replace
    calls = {"n": 0}

    def _failing_replace(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated replace failure")
        real_replace(src, dst)

    monkeypatch.setattr(
        "ai_platform_generator.adapters.repo.filesystem.os.replace", _failing_replace
    )

    with pytest.raises(Exception):
        repo.save(bundle)

    # First artefact's tmp must be cleaned up; final file must not exist.
    assert not (target / "openapi.json").exists()
    assert not (target / "openapi.json.tmp").exists()
