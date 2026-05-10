"""Error-translation tests for :class:`KindClusterRuntime`.

The kind adapter is the place where low-level subprocess outcomes
(``returncode``, ``TimeoutExpired``, ``FileNotFoundError``) become typed
domain errors. This file pins down the mapping documented in
``docs/ddd/bounded-contexts/04-cluster-provisioning.md`` section 9.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime
from ai_platform_generator.domain.errors import (
    ClusterCreationTimedOut,
    KubectlInvocationFailed,
    PrerequisiteMissing,
)


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def _make_cluster(name: str = "demo") -> Any:
    return SimpleNamespace(name=name, runtime="kind")


def _make_gvk() -> Any:
    return SimpleNamespace(api_version="example.io/v1", kind="Widget")


# ----------------------------------------------------------------------
# Non-zero exit → KubectlInvocationFailed
# ----------------------------------------------------------------------


def test_apply_nonzero_returns_failed_apply_result(tmp_path: Path) -> None:
    """A non-zero ``kubectl apply`` is reported as ``ApplyResult.success=False``."""
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="error: invalid yaml")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    manifest = tmp_path / "x.yaml"
    manifest.write_text("noop")

    result = runtime.apply(_make_cluster(), manifest)
    assert result.success is False
    assert "invalid yaml" in result.stderr


def test_describe_nonzero_raises_kubectl_invocation_failed() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="not found")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(KubectlInvocationFailed) as ei:
        runtime.describe(_make_cluster(), _make_gvk(), "foo", namespace="default")
    assert ei.value.code == "E_CLUSTER_KUBECTL_FAILED"
    assert "not found" in ei.value.user_message


def test_events_nonzero_raises_kubectl_invocation_failed() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="forbidden")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(KubectlInvocationFailed):
        runtime.events(_make_cluster())


def test_create_cluster_nonzero_raises_kubectl_invocation_failed() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="cluster already exists")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(KubectlInvocationFailed) as ei:
        runtime.create_cluster("demo", config=SimpleNamespace(name="demo"))
    assert "cluster already exists" in ei.value.user_message


def test_kubectl_failure_message_is_truncated() -> None:
    """Massive stderr must be truncated before going into ``user_message``."""
    big_stderr = "X" * 10_000
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr=big_stderr)

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(KubectlInvocationFailed) as ei:
        runtime.events(_make_cluster())
    # 2 KiB cap + small overhead for the prefix.
    assert len(ei.value.user_message) < 4_000
    assert "truncated" in ei.value.user_message.lower()


# ----------------------------------------------------------------------
# TimeoutExpired → ClusterCreationTimedOut (only for create)
# ----------------------------------------------------------------------


def test_create_cluster_timeout_raises_cluster_creation_timed_out() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_s)

    runtime = KindClusterRuntime(
        subprocess_runner=runner, cluster_create_timeout_s=42.0,
    )
    with pytest.raises(ClusterCreationTimedOut) as ei:
        runtime.create_cluster("demo", config=SimpleNamespace(name="demo"))
    assert ei.value.code == "E_CLUSTER_CREATION_TIMEOUT"
    assert "42" in ei.value.user_message


def test_delete_cluster_timeout_raises_cluster_creation_timed_out() -> None:
    """Delete timeouts use the same typed error class."""
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_s)

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(ClusterCreationTimedOut):
        runtime.delete_cluster("demo")


# ----------------------------------------------------------------------
# FileNotFoundError → PrerequisiteMissing
# ----------------------------------------------------------------------


def test_filenotfound_translates_to_prerequisite_missing(tmp_path: Path) -> None:
    """A missing binary is a configuration problem, not a kubectl failure."""
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        raise FileNotFoundError(2, "No such file", argv[0])

    runtime = KindClusterRuntime(subprocess_runner=runner)
    manifest = tmp_path / "x.yaml"
    manifest.write_text("noop")
    with pytest.raises(PrerequisiteMissing) as ei:
        runtime.apply(_make_cluster(), manifest)
    assert "kubectl" in ei.value.missing_tools


# ----------------------------------------------------------------------
# delete_cluster idempotency on "not found"
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "stderr",
    [
        "no such cluster: demo",
        "could not find a cluster named demo",
        "ERROR: no kind clusters found",
        "Error: cluster demo not found",
    ],
)
def test_delete_cluster_swallows_not_found(stderr: str) -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr=stderr)

    runtime = KindClusterRuntime(subprocess_runner=runner)
    # Must not raise.
    runtime.delete_cluster("demo")


def test_delete_cluster_unknown_failure_still_raises() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="Error: docker daemon refused connection")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    with pytest.raises(KubectlInvocationFailed):
        runtime.delete_cluster("demo")


# ----------------------------------------------------------------------
# check_prerequisites translation
# ----------------------------------------------------------------------


def test_check_prerequisites_reports_each_missing_tool() -> None:
    sequence: list[Any] = [
        FileNotFoundError(2, "No such file", "kind"),
        _completed(returncode=0),  # kubectl ok
        _completed(returncode=1, stderr="cannot connect to docker daemon"),
    ]

    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        item = sequence.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    runtime = KindClusterRuntime(subprocess_runner=runner)
    missing = runtime.check_prerequisites()
    names = {m.name for m in missing}
    assert "kind" in names
    assert "docker" in names
    assert "kubectl" not in names


def test_check_prerequisites_handles_probe_timeout() -> None:
    sequence: list[Any] = [
        subprocess.TimeoutExpired(cmd=["kind", "version"], timeout=10.0),
        _completed(returncode=0),
        _completed(returncode=0),
    ]

    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        item = sequence.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    runtime = KindClusterRuntime(subprocess_runner=runner)
    missing = runtime.check_prerequisites()
    assert any(m.name == "kind" for m in missing)
