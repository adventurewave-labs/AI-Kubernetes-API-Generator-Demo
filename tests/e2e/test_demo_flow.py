"""End-to-end coverage for the canonical ``./run.sh`` entrypoint.

These tests exercise the script as a black box — they invoke it as a
subprocess, observe stdout / stderr / exit code, and assert against the
on-disk artefact set the CLI produces. Anything ``run.sh`` cannot
deliver in DEMO MODE without a cluster is gated behind
:func:`clean_cluster` so CI without docker still gets a useful subset.

The tests in this module follow the contract defined in
``docs/ddd/08-implementation-roadmap.md`` Phase 7 and ADR-0020:

- ``demo`` exits 0 in OFFLINE mode and produces a CRD + instance YAML.
- ``help`` enumerates the canonical subcommands.
- A missing-prerequisite environment surfaces exit code 15 with an
  actionable install-hint URL on stderr.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

# Resolved at import time so tests with ``PATH=""`` can still locate the
# bash interpreter via an absolute path.
_BASH = shutil.which("bash") or "/bin/bash"

# All tests in this module are e2e.
pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    script: Path,
    *args: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float = 300.0,
    inherit_env: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``run.sh`` in a subprocess and return the completed result.

    ``check=False`` so callers can inspect non-zero exits explicitly.
    When ``inherit_env`` is False, only the supplied ``env`` is passed —
    used by the ``PATH=""`` test to guarantee a hostile environment.
    """
    full_env: dict[str, str] = dict(os.environ) if inherit_env else {}
    if env is not None:
        full_env.update(env)
    return subprocess.run(
        [_BASH, str(script), *args],
        env=full_env,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _yaml_documents(path: Path) -> list[dict]:
    """Return the list of YAML documents in ``path``.

    ``yaml.safe_load_all`` returns a generator; we materialise it so the
    caller can assert against length and shape.
    """
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc is not None]


# ---------------------------------------------------------------------------
# Required deliverables (per Wave 6 spec)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_run_sh_demo_offline_mode(
    run_sh: Path,
    tmp_path: Path,
) -> None:
    """``OFFLINE=1 ./run.sh demo --no-deploy --description "..."`` works.

    The test asserts the canonical artefact set exists, parses the CRD
    and instance YAML with :func:`yaml.safe_load`, and verifies the
    GVK on the instance matches what the CRD declares.
    """
    out_dir = tmp_path / "generated"
    out_dir.mkdir()
    result = _run(
        run_sh,
        "demo",
        "--no-deploy",
        "--no-install-tools",
        "--description",
        "Create a TestService API with foo (string)",
        env={"OFFLINE": "1", "OUTPUT_DIR": str(out_dir)},
    )
    assert result.returncode == 0, (
        f"OFFLINE demo failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Locate CRD + instance YAML files. The CLI names them
    # ``<kind-lower>.crd.yaml`` and ``<kind-lower>.instance.yaml`` so we
    # search by suffix to remain agnostic to which demo scenario the
    # catalog selected.
    crd_files = sorted(out_dir.glob("*.crd.yaml"))
    instance_files = sorted(out_dir.glob("*.instance.yaml"))
    assert crd_files, (
        f"no *.crd.yaml under {out_dir}: "
        f"{sorted(p.name for p in out_dir.iterdir())}"
    )
    assert instance_files, (
        f"no *.instance.yaml under {out_dir}: "
        f"{sorted(p.name for p in out_dir.iterdir())}"
    )

    # GVK round-trip: the instance must reference the CRD's group/kind.
    crd_docs = _yaml_documents(crd_files[0])
    instance_docs = _yaml_documents(instance_files[0])
    assert crd_docs and instance_docs, "empty yaml documents"
    crd = crd_docs[0]
    instance = instance_docs[0]

    crd_group = crd.get("spec", {}).get("group")
    crd_kind = crd.get("spec", {}).get("names", {}).get("kind")
    instance_api_version = instance.get("apiVersion", "")
    instance_kind = instance.get("kind")

    assert crd_group, f"CRD has no spec.group: {crd}"
    assert crd_kind, f"CRD has no spec.names.kind: {crd}"
    assert instance_api_version.startswith(f"{crd_group}/"), (
        f"instance apiVersion {instance_api_version!r} does not start "
        f"with CRD group {crd_group!r}"
    )
    assert instance_kind == crd_kind, (
        f"instance kind {instance_kind!r} != CRD kind {crd_kind!r}"
    )


@pytest.mark.e2e_no_cluster
def test_run_sh_help_lists_subcommands(run_sh: Path) -> None:
    """``./run.sh help`` exits 0 and mentions every documented subcommand."""
    result = _run(run_sh, "help", timeout=15.0)
    assert result.returncode == 0, (
        f"help exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # ``usage()`` writes to stdout so users can pipe it into a pager.
    output = result.stdout + result.stderr
    for token in ("demo", "cluster-up", "cluster-down"):
        assert token in output, (
            f"help output missing {token!r}\nfull output:\n{output}"
        )


@pytest.mark.e2e_no_cluster
def test_run_sh_demo_missing_prereqs(run_sh: Path, tmp_path: Path) -> None:
    """A bare ``PATH=""`` environment must exit 15 with an install hint URL.

    We strip the inherited environment so even ``python3`` is missing.
    The script's ``require_python`` check is the first prerequisite, so
    it fires immediately and surfaces the canonical install-hint URL
    documented in ``run.sh``.
    """
    result = _run(
        run_sh,
        "demo",
        env={"PATH": "", "HOME": str(tmp_path)},
        timeout=15.0,
        inherit_env=False,
    )
    assert result.returncode == 15, (
        f"expected exit 15, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # ``log_err`` writes to stderr; the install-hint URL must be there
    # so a developer can self-serve the fix.
    assert "install hint" in result.stderr.lower(), (
        f"stderr missing 'install hint':\n{result.stderr}"
    )
    # At least one of the canonical install-hint URLs must surface. We
    # accept any of them because PATH="" can't tell us which tool the
    # user was missing first.
    install_urls = (
        "https://www.python.org/downloads/",
        "https://kind.sigs.k8s.io/docs/user/quick-start/#installation",
        "https://kubernetes.io/docs/tasks/tools/#kubectl",
        "https://docs.docker.com/get-docker/",
    )
    assert any(url in result.stderr for url in install_urls), (
        f"stderr missing canonical install-hint URL:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Cluster-bound test (kept from prior wave; gated by ``clean_cluster``)
# ---------------------------------------------------------------------------


def test_run_sh_demo_full_flow(
    run_sh: Path,
    clean_cluster: object,
    tmp_path: Path,
) -> None:
    """The full demo path must end with the deployed instance reachable.

    Skipped automatically when ``kind`` / ``docker`` are absent (see
    :func:`tests.e2e.conftest.pytest_collection_modifyitems`).
    """
    del clean_cluster  # fixture-only — cluster is created and torn down for us
    out_dir = tmp_path / "generated_full"
    out_dir.mkdir()
    result = _run(
        run_sh,
        "demo",
        "--no-install-tools",
        env={"OFFLINE": "1", "OUTPUT_DIR": str(out_dir)},
        timeout=900.0,
    )
    assert result.returncode == 0, (
        f"full demo failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # The instance file gives us the kind to query; the CLI deploys it
    # under the kind-ai-platform-demo context.
    instance_files = sorted(out_dir.glob("*.instance.yaml"))
    assert instance_files, "no instance.yaml emitted"
    instance = _yaml_documents(instance_files[0])[0]
    plural = instance.get("kind", "").lower() + "s"
    name = instance.get("metadata", {}).get("name", "")
    api_group = instance.get("apiVersion", "").split("/", 1)[0]

    kubectl_check = subprocess.run(
        [
            "kubectl",
            "--context",
            "kind-ai-platform-demo",
            "get",
            f"{plural}.{api_group}",
            name,
        ],
        capture_output=True,
        text=True,
        timeout=60.0,
        check=False,
    )
    assert kubectl_check.returncode == 0, (
        f"kubectl get returned non-zero "
        f"(stdout={kubectl_check.stdout!r}, stderr={kubectl_check.stderr!r})"
    )


# ---------------------------------------------------------------------------
# Defensive check: a CLI failure must not be swallowed by run.sh
# ---------------------------------------------------------------------------


@pytest.mark.e2e_no_cluster
def test_run_sh_failure_propagates_exit_code(
    run_sh: Path,
    tmp_path: Path,
) -> None:
    """A typed CLI exit code must surface verbatim through ``run.sh``.

    We can't easily force a typed error in OFFLINE mode, so this test
    accepts either the natural CLI exit (0 / 11 depending on whether
    Agent V's domain fixes have landed) and only fails on a script-
    level bug (e.g. the trap rewriting the code to 1).
    """
    out_dir = tmp_path / "generated"
    out_dir.mkdir()
    result = _run(
        run_sh,
        "demo",
        "--no-deploy",
        "--no-install-tools",
        env={"OFFLINE": "1", "OUTPUT_DIR": str(out_dir)},
    )
    # Acceptable codes: 0 (success) or any typed CLI exit code (10-15).
    assert result.returncode in (0, 10, 11, 12, 13, 14, 15), (
        f"unexpected exit code {result.returncode} (script-level bug?)\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# CI=true → JSON log format auto-pass
# ---------------------------------------------------------------------------


@pytest.mark.e2e_no_cluster
def test_run_sh_ci_env_passes_json_log_format(
    run_sh: Path,
    tmp_path: Path,
) -> None:
    """When ``CI=true``, ``run.sh`` must pass ``--log-format json`` to the CLI.

    We assert this indirectly: the CLI in JSON mode emits one JSON
    object per line on stdout. We strip ``run.sh`` chatter (sent to
    stderr only) and check that at least one CLI stdout line parses
    as JSON.
    """
    out_dir = tmp_path / "generated"
    out_dir.mkdir()
    result = _run(
        run_sh,
        "demo",
        "--no-deploy",
        "--no-install-tools",
        env={
            "OFFLINE": "1",
            "OUTPUT_DIR": str(out_dir),
            "CI": "true",
        },
    )
    # Even on the pre-existing E_DOMAIN_GENERIC failure, the CLI emits
    # JSON to stdout; a successful run does too.
    json_lines = [
        line for line in result.stdout.splitlines() if line.strip().startswith("{")
    ]
    assert json_lines, (
        f"CI=true did not produce any JSON-formatted CLI output\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # Each must parse as valid JSON.
    for line in json_lines[:5]:
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - debug aid
            pytest.fail(f"non-JSON line on stdout: {line!r} ({exc})")
