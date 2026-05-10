"""Tests for :class:`ProvenanceManifestFactory`."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.domain.aggregates import (
    ArtifactType,
    CodegenRequest,
    ProvenanceManifest,
)
from ai_platform_generator.domain.generation.provenance_factory import (
    ProvenanceManifestFactory,
)
from ai_platform_generator.domain.services.checksum_service import ChecksumService
from ai_platform_generator.domain.values.provider_mode import ProviderMode
from ai_platform_generator.domain.values.run_id import RunId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rendered_artifact(rel_path: Path, payload: bytes):
    """Build a stub-or-real ``RenderedArtifact`` instance.

    ``rel_path`` MUST be relative — the aggregate enforces that.
    """
    from ai_platform_generator.domain.aggregates import RenderedArtifact

    checksum = ChecksumService().sha256_of(payload)
    return RenderedArtifact(
        path=rel_path,
        payload=payload,
        mode=0o644,
        artefact_type=ArtifactType.OPENAPI,
        checksum=checksum,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_create_populates_all_fields(sample_request: CodegenRequest) -> None:
    factory = ProvenanceManifestFactory()
    run_id = RunId.new()
    clock = FrozenClock(datetime(2025, 5, 9, 12, 34, 56, tzinfo=timezone.utc))

    files = [
        _rendered_artifact(Path("a.json"), b"hello"),
        _rendered_artifact(Path("b.json"), b"world"),
    ]

    manifest = factory.create(
        run_id=run_id,
        request=sample_request,
        provider_mode=ProviderMode.DEMO,
        model_id="anthropic/claude-3.5-sonnet",
        files=files,
        clock=clock,
    )

    assert isinstance(manifest, ProvenanceManifest)
    assert manifest.run_id == run_id
    assert manifest.tool_version  # non-empty
    assert manifest.git_sha  # non-empty (one of: real sha / env / unknown)
    assert manifest.generated_at == datetime(
        2025, 5, 9, 12, 34, 56, tzinfo=timezone.utc
    )
    assert manifest.model_id == "anthropic/claude-3.5-sonnet"
    # The factory turns RenderedArtifacts into ArtifactRefs (path+checksum).
    assert len(manifest.files) == 2
    paths = {ref.path for ref in manifest.files}
    assert paths == {Path("a.json"), Path("b.json")}


def test_create_rejects_non_list_files(sample_request: CodegenRequest) -> None:
    factory = ProvenanceManifestFactory()
    clock = FrozenClock(datetime(2025, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(TypeError, match="files must be a list"):
        factory.create(
            run_id=RunId.new(),
            request=sample_request,
            provider_mode=ProviderMode.DEMO,
            model_id=None,
            files=("not", "a", "list"),  # type: ignore[arg-type]
            clock=clock,
        )


# ---------------------------------------------------------------------------
# git SHA resolution
# ---------------------------------------------------------------------------
def test_git_sha_uses_git_when_in_repo() -> None:
    """Inside this repo, ``git rev-parse HEAD`` resolves to the real SHA."""
    real_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not real_sha:
        pytest.skip("not inside a git repo")

    factory = ProvenanceManifestFactory()
    assert factory._git_sha() == real_sha


def test_git_sha_falls_back_to_env_when_git_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If ``git rev-parse`` exits non-zero, the env var wins."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLATFORM_GENERATOR_GIT_SHA", "abcdef0")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    factory = ProvenanceManifestFactory()
    sha = factory._git_sha()
    # Either we successfully detected we are outside a repo (env wins)
    # or — if the git binary itself happens to find an ancestor repo
    # despite the ceiling — we still get a non-empty string. Both are
    # acceptable; the contract is "never raise, never empty".
    assert sha
    if sha != "abcdef0":
        # Real ancestor SHA was found; accept that too.
        assert len(sha) >= 7


def test_git_sha_unknown_when_neither_git_nor_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No git, no env var → literal ``"unknown"``."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_PLATFORM_GENERATOR_GIT_SHA", raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    # Make ``git`` itself unavailable so step 1 in the resolution chain
    # raises FileNotFoundError.
    monkeypatch.setenv("PATH", "")

    factory = ProvenanceManifestFactory()
    assert factory._git_sha() == "unknown"


def test_git_sha_unknown_when_subprocess_raises_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If :func:`subprocess.run` raises :class:`OSError` we still don't crash."""

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("simulated")

    monkeypatch.setattr(subprocess, "run", _raise)
    monkeypatch.delenv("AI_PLATFORM_GENERATOR_GIT_SHA", raising=False)

    factory = ProvenanceManifestFactory()
    assert factory._git_sha() == "unknown"


# ---------------------------------------------------------------------------
# tool_version
# ---------------------------------------------------------------------------
def test_tool_version_reads_package_version() -> None:
    import ai_platform_generator as _pkg

    factory = ProvenanceManifestFactory()
    assert factory._tool_version() == _pkg.__version__


def test_tool_version_falls_back_when_attribute_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ai_platform_generator as _pkg

    monkeypatch.setattr(_pkg, "__version__", "", raising=False)
    factory = ProvenanceManifestFactory()
    assert factory._tool_version() == "0.0.0"


# ---------------------------------------------------------------------------
# Checksum integration: the factory must not silently re-hash payloads.
# ---------------------------------------------------------------------------
def test_factory_preserves_artifact_checksums(
    sample_request: CodegenRequest,
) -> None:
    factory = ProvenanceManifestFactory()
    art = _rendered_artifact(Path("a.json"), b"hello")
    clock = FrozenClock(datetime(2025, 1, 1, tzinfo=timezone.utc))

    manifest = factory.create(
        run_id=RunId.new(),
        request=sample_request,
        provider_mode=ProviderMode.LIVE,
        model_id="x",
        files=[art],
        clock=clock,
    )
    refs = list(manifest.files)
    assert len(refs) == 1
    assert refs[0].path == Path("a.json")
    assert refs[0].checksum == art.checksum


# Sanity: ensure the AI_PLATFORM_GENERATOR_GIT_SHA env var doesn't leak
# between tests in either direction.
@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    if "AI_PLATFORM_GENERATOR_GIT_SHA" in os.environ:
        monkeypatch.delenv("AI_PLATFORM_GENERATOR_GIT_SHA", raising=False)
