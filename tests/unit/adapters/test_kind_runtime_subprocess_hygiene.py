"""Subprocess-hygiene tests for :class:`KindClusterRuntime`.

These tests are the security-relevant unit tests for the kind adapter:
they pin down ADR-0020's invariants. Concretely, every public method
must

* construct argv as a ``list[str]`` (no bytes, no Path, no None);
* never rely on ``shell=True`` semantics — argv goes straight to the
  kernel, so shell metacharacters in user input must travel through as
  literal data;
* always pass a non-zero ``timeout_s``.

The ``subprocess_runner`` injection seam lets us assert all of this
without spawning a real subprocess.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime
from ai_platform_generator.ports.cluster_runtime import (
    ClusterStatus,
)


class _RecordingRunner:
    """Captures every subprocess invocation for later assertions."""

    def __init__(
        self,
        *,
        responses: list[subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses or [])

    def __call__(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        env: Any = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append({"argv": argv, "timeout_s": timeout_s, "env": env})
        if self._responses:
            return self._responses.pop(0)
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _make_cluster(name: str = "demo") -> Any:
    return SimpleNamespace(name=name, runtime="kind", nodes=())


def _make_gvk() -> Any:
    return SimpleNamespace(api_version="example.io/v1", kind="Widget")


# ----------------------------------------------------------------------
# Per-method hygiene assertions
# ----------------------------------------------------------------------


def _assert_argv_clean(argv: Any, *, timeout_s: float) -> None:
    assert isinstance(argv, list), f"argv must be list, got {type(argv).__name__}"
    assert argv, "argv must not be empty"
    for entry in argv:
        assert isinstance(entry, str), (
            f"argv entries must be str, found {type(entry).__name__}: {entry!r}"
        )
    # Sanity: argv[0] is a tool name, never a shell path.
    assert argv[0] not in {"/bin/sh", "/bin/bash", "sh", "bash"}, (
        f"argv must not invoke a shell, got argv[0]={argv[0]!r}"
    )
    assert timeout_s > 0


def test_check_prerequisites_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(responses=[_ok(), _ok(), _ok()])
    runtime = KindClusterRuntime(subprocess_runner=runner)

    runtime.check_prerequisites()

    assert len(runner.calls) == 3
    for call in runner.calls:
        _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    # Tool-specific probe shapes
    assert runner.calls[0]["argv"][0] == "kind"
    assert runner.calls[1]["argv"][:3] == ["kubectl", "version", "--client"]
    assert runner.calls[2]["argv"][:2] == ["docker", "version"]


def test_cluster_status_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(
        responses=[
            _ok(stdout="demo\n"),  # kind get clusters
            _ok(stdout="control-plane\n"),  # kubectl get nodes
            _ok(stdout="Kubernetes control plane is running"),  # cluster-info
        ]
    )
    runtime = KindClusterRuntime(subprocess_runner=runner)
    status = runtime.cluster_status("demo")

    assert isinstance(status, ClusterStatus)
    for call in runner.calls:
        _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])


def test_create_cluster_argv_is_clean_strings(tmp_path: Path) -> None:
    runner = _RecordingRunner(
        responses=[
            _ok(),  # kind create cluster
            _ok(stdout="demo\n"),  # cluster_status: kind get clusters
            _ok(stdout="control-plane\n"),  # kubectl get nodes
            _ok(),  # kubectl cluster-info
        ]
    )
    runtime = KindClusterRuntime(subprocess_runner=runner, kubeconfig_dir=tmp_path)
    cluster = runtime.create_cluster("demo", config=SimpleNamespace(name="demo"))

    assert cluster.name == "demo"
    for call in runner.calls:
        _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    create_argv = runner.calls[0]["argv"]
    assert create_argv[:5] == ["kind", "create", "cluster", "--name", "demo"]
    assert "--config" in create_argv
    assert "--wait" in create_argv


def test_delete_cluster_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(responses=[_ok()])
    runtime = KindClusterRuntime(subprocess_runner=runner)
    runtime.delete_cluster("demo")

    [call] = runner.calls
    _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    assert call["argv"] == ["kind", "delete", "cluster", "--name", "demo"]


def test_apply_argv_is_clean_strings(tmp_path: Path) -> None:
    runner = _RecordingRunner(responses=[_ok(stdout="widget.example.io/foo created\n")])
    runtime = KindClusterRuntime(subprocess_runner=runner)
    manifest = tmp_path / "widget.yaml"
    manifest.write_text("apiVersion: example.io/v1\nkind: Widget\nmetadata: {name: foo}\n")

    runtime.apply(_make_cluster(), manifest)
    [call] = runner.calls
    _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    assert "kubectl" == call["argv"][0]
    assert "apply" in call["argv"]
    assert str(manifest) in call["argv"]


def test_get_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(responses=[_ok(stdout="foo\tRunning")])
    runtime = KindClusterRuntime(subprocess_runner=runner)
    runtime.get(_make_cluster(), _make_gvk(), "foo", namespace="default")

    [call] = runner.calls
    _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    assert "kubectl" == call["argv"][0]
    assert "get" in call["argv"]
    assert "Widget" in call["argv"]
    assert "foo" in call["argv"]
    assert "-n" in call["argv"]


def test_describe_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(responses=[_ok(stdout="Name: foo")])
    runtime = KindClusterRuntime(subprocess_runner=runner)
    runtime.describe(_make_cluster(), _make_gvk(), "foo", namespace=None)

    [call] = runner.calls
    _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    assert call["argv"][:4] == ["kubectl", "describe", "Widget", "foo"]
    # No -n when namespace is None
    assert "-n" not in call["argv"]


def test_events_argv_is_clean_strings() -> None:
    runner = _RecordingRunner(responses=[_ok(stdout=json.dumps({"items": []}))])
    runtime = KindClusterRuntime(subprocess_runner=runner)
    runtime.events(_make_cluster())

    [call] = runner.calls
    _assert_argv_clean(call["argv"], timeout_s=call["timeout_s"])
    assert call["argv"][:5] == ["kubectl", "get", "events", "-o", "json"]


# ----------------------------------------------------------------------
# Shell-metachar pass-through
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil_name",
    [
        "demo;rm -rf /",
        "demo$(whoami)",
        "demo`id`",
        "demo|cat /etc/passwd",
        "demo&&echo pwn",
        "demo\nnewline",
        "demo space",
    ],
)
def test_evil_cluster_names_are_passed_verbatim(evil_name: str) -> None:
    """Cluster names with shell metachars must travel as a single argv entry.

    With ``shell=False`` the OS treats argv[i] as opaque data, so the
    substring ``;rm -rf /`` cannot break out and run a second command.
    The contract here is purely: kind/kubectl receive the *exact* string,
    untouched.
    """
    runner = _RecordingRunner(responses=[_ok()])
    runtime = KindClusterRuntime(subprocess_runner=runner)

    runtime.delete_cluster(evil_name)

    [call] = runner.calls
    argv = call["argv"]
    _assert_argv_clean(argv, timeout_s=call["timeout_s"])
    # The evil name must appear as a single argv entry, byte-for-byte.
    assert evil_name in argv
    name_index = argv.index(evil_name)
    assert argv[name_index - 1] == "--name"
    # And no other argv entry contains a chunk of the evil name.
    for index, entry in enumerate(argv):
        if index == name_index:
            continue
        assert evil_name not in entry, (
            "evil name must not be smuggled into another argv entry"
        )


def test_runner_helper_rejects_non_string_argv() -> None:
    """The default runner refuses non-string argv as defence-in-depth."""
    from ai_platform_generator.adapters.runtime.kind import _run_subprocess

    with pytest.raises(ValueError, match="argv\\[1\\] must be str"):
        _run_subprocess(["echo", 42], timeout_s=1.0)  # type: ignore[list-item]
