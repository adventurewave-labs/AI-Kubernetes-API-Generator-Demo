"""Drive the CLI as a real subprocess.

Click's :class:`CliRunner` is great for unit-level coverage but it
re-uses the in-process interpreter, masking packaging defects (broken
console-script entry, missing ``__main__``, import-time side effects,
etc.). The tests in this module deliberately fork a *fresh*
interpreter so we exercise the same wire surface a user would.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _python_cli(
    *args: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m ai_platform_generator.adapters.cli.main`` in a subprocess."""
    full_env = dict(os.environ)
    if env is not None:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "ai_platform_generator.adapters.cli.main", *args],
        env=full_env,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.e2e_no_cluster
def test_cli_help_via_subprocess() -> None:
    """``--help`` must exit 0 and mention the tool name."""
    result = _python_cli("--help")
    assert result.returncode == 0, (
        f"--help failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "ai-platform-generator" in result.stdout.lower() \
        or "AI Kubernetes API" in result.stdout \
        or "Usage" in result.stdout


@pytest.mark.e2e_no_cluster
def test_cli_examples_via_subprocess() -> None:
    """``examples`` must list all eight built-in scenarios."""
    result = _python_cli("examples")
    assert result.returncode == 0, (
        f"examples failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    expected_scenarios = [
        "postgres-cluster",
        "redis-cluster",
        "vector-db",
        "notebook",
        "database-backup",
        "cache-cluster",
        "monitoring-service",
        "ml-pipeline",
    ]
    output = result.stdout
    missing = [name for name in expected_scenarios if name not in output]
    assert not missing, (
        f"examples output is missing {missing}\nfull stdout:\n{output}"
    )


@pytest.mark.e2e_no_cluster
def test_cli_generate_demo_no_deploy_via_subprocess(tmp_output_dir: Path) -> None:
    """A no-deploy demo run must produce the canonical artefact set."""
    intent = (
        "PostgreSQL cluster API with replicas (int 1-7), tlsEnabled (bool), "
        "and backupSchedule (cron string)"
    )
    result = _python_cli(
        "--llm-provider=demo",
        "--no-deploy",
        "--output-dir",
        str(tmp_output_dir),
        "generate",
        intent,
    )
    assert result.returncode == 0, (
        f"generate failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    expected = [
        "openapi.json",
        "postgrescluster.crd.yaml",
        "postgrescluster.instance.yaml",
        "manifest.json",
    ]
    missing = [name for name in expected if not (tmp_output_dir / name).exists()]
    assert not missing, (
        f"missing artefacts under {tmp_output_dir}: {missing}\n"
        f"contents: {sorted(p.name for p in tmp_output_dir.iterdir())}"
    )

    manifest = json.loads((tmp_output_dir / "manifest.json").read_text())
    assert manifest.get("provider_mode") == "demo", (
        f"expected provider_mode=demo, got {manifest.get('provider_mode')!r}"
    )
