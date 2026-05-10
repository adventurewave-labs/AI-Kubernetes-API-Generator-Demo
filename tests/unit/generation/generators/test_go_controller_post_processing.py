"""Unit tests for :class:`GoControllerGenerator._post_process`.

The post-processing step runs ``gofmt`` on every ``.go`` file when the
binary is on PATH. On any failure (binary missing, non-zero exit, time
out, vanished mid-run) the unformatted bytes must be kept and a
warning written to ``stderr`` — formatting is a hygiene step and must
never gate generation success (per ADR-0011 + ADR-0020 hygiene).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ai_platform_generator.domain.aggregates import CodegenRequest, OpenAPIDocument
from ai_platform_generator.domain.generation.generators.go_controller import (
    CONTROLLER_SUBDIR,
    GoControllerGenerator,
)
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile
from ai_platform_generator.domain.values import (
    GVK,
    Group,
    Kind,
    OutputPath,
    PropertyConstraints,
    PropertyType,
    ProviderMode,
    SpecProperty,
    Version,
)


# ----------------------------------------------------------------------
# Minimal IR fixture
# ----------------------------------------------------------------------
@pytest.fixture
def ir(tmp_path: Path) -> OpenAPIDocument:
    req = CodegenRequest(
        gvk=GVK(group=Group("example.com"), version=Version("v1"), kind=Kind("Widget")),
        spec_properties=(
            SpecProperty(
                name="size",
                type=PropertyType.INTEGER,
                description="Number of widgets.",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=tmp_path, relative=Path(".")),
        description="A widget.",
        provider_mode=ProviderMode.DEMO,
    )
    return OpenAPIDocument.from_request(req)


# ----------------------------------------------------------------------
# Hand-rolled rendered files (cheap; no need to round-trip the IR)
# ----------------------------------------------------------------------
def _sample_files(target: Path) -> tuple[_RenderedFile, ...]:
    sub = target / CONTROLLER_SUBDIR
    return (
        _RenderedFile(
            path=sub / "main.go",
            payload=b"package main\nfunc  main(){\n}\n",  # double-space to test gofmt
        ),
        _RenderedFile(path=sub / "Dockerfile", payload=b"FROM scratch\n"),
        _RenderedFile(path=sub / "go.mod", payload=b"module x\ngo 1.22\n"),
    )


# ----------------------------------------------------------------------
# gofmt invoked when present
# ----------------------------------------------------------------------
def test_gofmt_invoked_for_go_files_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invocations: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: "/usr/local/bin/gofmt",
    )

    formatted = b"package main\n\nfunc main() {}\n"

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        invocations.append({"argv": argv, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=formatted, stderr=b""
        )

    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.subprocess.run",
        fake_run,
    )

    gen = GoControllerGenerator()
    out = gen._post_process(_sample_files(tmp_path))

    # gofmt was called exactly once — only for the .go file.
    assert len(invocations) == 1
    assert invocations[0]["argv"] == ["/usr/local/bin/gofmt"]
    assert invocations[0]["kwargs"]["shell"] is False
    # Formatted bytes replaced the .go payload.
    main_go = next(f for f in out if f.path.name == "main.go")
    assert main_go.payload == formatted
    # Non-Go files passed through verbatim.
    assert next(f for f in out if f.path.name == "Dockerfile").payload == (
        b"FROM scratch\n"
    )


# ----------------------------------------------------------------------
# gofmt missing: graceful skip with stderr warning
# ----------------------------------------------------------------------
def test_gofmt_missing_keeps_unformatted_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: None,
    )

    sample = _sample_files(tmp_path)
    gen = GoControllerGenerator()
    out = gen._post_process(sample)

    # Bytes are unchanged.
    assert tuple(f.payload for f in out) == tuple(f.payload for f in sample)

    err = capsys.readouterr().err
    assert "gofmt not found" in err


# ----------------------------------------------------------------------
# gofmt non-zero exit: keep unformatted bytes, log warning
# ----------------------------------------------------------------------
def test_gofmt_failure_keeps_unformatted_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: "/usr/local/bin/gofmt",
    )

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=argv,
            returncode=2,
            stdout=b"",
            stderr=b"main.go:1: expected 'package'",
        )

    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.subprocess.run",
        fake_run,
    )

    sample = _sample_files(tmp_path)
    gen = GoControllerGenerator()
    out = gen._post_process(sample)

    main_go = next(f for f in out if f.path.name == "main.go")
    original = next(f for f in sample if f.path.name == "main.go")
    assert main_go.payload == original.payload  # untouched

    err = capsys.readouterr().err
    assert "gofmt failed" in err
    assert "exit 2" in err


# ----------------------------------------------------------------------
# gofmt vanishes after PATH lookup: graceful FileNotFoundError handling
# ----------------------------------------------------------------------
def test_gofmt_filenotfound_during_run_is_swallowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: "/usr/local/bin/gofmt",
    )

    def fake_run(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError(2, "No such file", "/usr/local/bin/gofmt")

    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.subprocess.run",
        fake_run,
    )

    sample = _sample_files(tmp_path)
    gen = GoControllerGenerator()
    out = gen._post_process(sample)

    # No raise; bytes preserved.
    assert tuple(f.payload for f in out) == tuple(f.payload for f in sample)
    err = capsys.readouterr().err
    assert "gofmt vanished" in err


# ----------------------------------------------------------------------
# gofmt timeout: graceful TimeoutExpired handling
# ----------------------------------------------------------------------
def test_gofmt_timeout_is_swallowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: "/usr/local/bin/gofmt",
    )

    def fake_run(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="gofmt", timeout=10)

    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.subprocess.run",
        fake_run,
    )

    sample = _sample_files(tmp_path)
    gen = GoControllerGenerator()
    out = gen._post_process(sample)

    assert tuple(f.payload for f in out) == tuple(f.payload for f in sample)
    err = capsys.readouterr().err
    assert "timed out" in err


# ----------------------------------------------------------------------
# End-to-end: generator survives a missing gofmt binary
# ----------------------------------------------------------------------
def test_generate_works_without_gofmt(
    tmp_path: Path,
    ir: OpenAPIDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ai_platform_generator.domain.generation.generators.go_controller.shutil.which",
        lambda _name: None,
    )
    artefacts = GoControllerGenerator().generate(ir, tmp_path)
    assert len(artefacts) == 6
