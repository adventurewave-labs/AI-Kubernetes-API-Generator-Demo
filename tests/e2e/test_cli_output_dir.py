"""Regression coverage for absolute ``--output-dir`` handling.

Two CLI entry points (``build`` and ``interactive``) historically failed
when handed an *absolute* ``--output-dir``:

- ``build`` raised an uncaught ``InvalidOutputPath`` because it passed the
  absolute path as the ``relative`` component of an :class:`OutputPath`.
- both commands left the filesystem repository's traversal-safety root at
  ``cwd/generated`` while writing under the supplied absolute directory,
  yielding ``E_ARTIFACT_PATH_TRAVERSAL``.

These tests run the real composition root (demo provider, real filesystem
repository) via subprocess, so they exercise the exact path that broke.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_no_cluster]

_CLI = "ai_platform_generator.adapters.cli.main"

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _valid_request() -> dict:
    """A minimal-but-valid CodegenRequest payload for ``build``."""
    return {
        "gvk": {
            "group": "ai.platform.cnoe.io",
            "version": "v1alpha1",
            "kind": "VectorDB",
        },
        "spec_properties": [
            {
                "name": "replicas",
                "type": "integer",
                "description": "Number of replicas.",
                "constraints": {"minimum": 1, "maximum": 10},
            },
        ],
        "output_path": {
            "root": str(Path.cwd().resolve()),
            "relative": "generated/vector-db",
        },
        "description": "A vector database for AI workloads.",
        "provider_mode": "demo",
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["OFFLINE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", _CLI, *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120.0,
        check=False,
    )


def test_build_accepts_absolute_output_dir(tmp_path: Path) -> None:
    """``build`` writes a full bundle into an absolute ``--output-dir``."""
    req = tmp_path / "request.json"
    req.write_text(json.dumps(_valid_request()))
    out = tmp_path / "build-out"

    result = _run_cli(
        "--llm-provider=demo",
        "--no-deploy",
        "--output-dir",
        str(out),
        "--log-format",
        "quiet",
        "build",
        str(req),
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "E_ARTIFACT_PATH_TRAVERSAL" not in combined
    assert "InvalidOutputPath" not in combined
    assert (out / "vectordb.crd.yaml").is_file()
    assert (out / "manifest.json").is_file()


def test_interactive_accepts_absolute_output_dir(tmp_path: Path) -> None:
    """``interactive`` generates into an absolute ``--output-dir``."""
    out = tmp_path / "interactive-out"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            _CLI,
            "--llm-provider=demo",
            "--no-deploy",
            "--output-dir",
            str(out),
            "--log-format",
            "quiet",
            "interactive",
        ],
        cwd=str(_REPO_ROOT),
        env={**os.environ, "OFFLINE": "1"},
        input="postgres\nq\n",
        capture_output=True,
        text=True,
        timeout=120.0,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "E_ARTIFACT_PATH_TRAVERSAL" not in combined
    assert (out / "postgrescluster.crd.yaml").is_file()
