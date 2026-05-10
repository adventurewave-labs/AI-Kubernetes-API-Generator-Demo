"""Lifecycle tests for :class:`KindClusterRuntime`.

Wires the fake subprocess runner through a full create → apply → get →
events flow and asserts the resulting domain values transition the way
the cluster-provisioning context expects.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime
from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterEvent,
    ClusterStatus,
    ResourceState,
)


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


class _ScriptedRunner:
    """A subprocess runner that returns canned responses based on argv shape."""

    def __init__(self, script: list[tuple[str, subprocess.CompletedProcess[str]]]):
        # script: list of (matcher_substring, response)
        self.script = list(script)
        self.calls: list[list[str]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        env: Any = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        joined = " ".join(argv)
        for index, (matcher, response) in enumerate(self.script):
            if matcher in joined:
                # Pop on first match so successive identical calls fall
                # through to the next scripted entry.
                self.script.pop(index)
                return response
        return _completed()


def test_full_lifecycle_returns_expected_states(tmp_path: Path) -> None:
    """create → apply → get → events shape matches the port contract."""
    manifest = tmp_path / "widget.yaml"
    manifest.write_text("noop")

    events_payload = {
        "items": [
            {
                "type": "Normal",
                "reason": "Created",
                "message": "Created pod",
                "involvedObject": {"name": "demo-control-plane"},
                "metadata": {"creationTimestamp": "2026-05-10T00:00:00Z"},
            }
        ]
    }

    runner = _ScriptedRunner(
        script=[
            # create_cluster
            ("kind create cluster", _completed(stdout="created\n")),
            # cluster_status (called from create_cluster)
            ("kind get clusters", _completed(stdout="demo\n")),
            ("kubectl get nodes", _completed(stdout="demo-control-plane\n")),
            ("kubectl cluster-info", _completed(stdout="OK")),
            # apply
            (
                "kubectl apply",
                _completed(stdout=(
                    "customresourcedefinition.apiextensions.k8s.io/widgets created\n"
                    "widget.example.io/foo configured\n"
                )),
            ),
            # get
            ("kubectl get Widget", _completed(stdout="foo\tRunning")),
            # events
            ("kubectl get events", _completed(stdout=json.dumps(events_payload))),
        ]
    )

    runtime = KindClusterRuntime(subprocess_runner=runner)

    cluster = runtime.create_cluster("demo", config=SimpleNamespace(name="demo"))
    assert cluster.name == "demo"
    assert cluster.runtime == "kind"
    assert cluster.nodes == ("demo-control-plane",)

    apply_result = runtime.apply(cluster, manifest)
    assert isinstance(apply_result, ApplyResult)
    assert apply_result.success is True
    assert "customresourcedefinition.apiextensions.k8s.io/widgets" in apply_result.applied
    assert "widget.example.io/foo" in apply_result.applied

    state = runtime.get(
        cluster,
        SimpleNamespace(api_version="example.io/v1", kind="Widget"),
        "foo",
        namespace="default",
    )
    assert isinstance(state, ResourceState)
    assert state.found is True
    assert state.name == "foo"
    assert state.kind == "Widget"
    assert state.raw["status_text"] == "Running"

    events = runtime.events(cluster)
    assert len(events) == 1
    [event] = events
    assert isinstance(event, ClusterEvent)
    assert event.reason == "Created"
    assert event.involved_object == "demo-control-plane"
    assert isinstance(event.timestamp, datetime)


def test_cluster_status_reports_absent_cluster() -> None:
    """A name not in ``kind get clusters`` must yield ``exists=False``."""
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(stdout="other\n")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    status = runtime.cluster_status("demo")
    assert isinstance(status, ClusterStatus)
    assert status.exists is False
    assert status.ready is False
    assert status.nodes == ()


def test_cluster_status_present_but_not_ready() -> None:
    """If kubectl cannot reach the cluster we report exists=True, ready=False."""
    sequence: list[subprocess.CompletedProcess[str]] = [
        _completed(stdout="demo\n"),  # kind get clusters
        _completed(stdout="demo-control-plane\n"),  # kubectl get nodes
        _completed(returncode=1, stderr="connection refused"),  # cluster-info
    ]

    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return sequence.pop(0)

    runtime = KindClusterRuntime(subprocess_runner=runner)
    status = runtime.cluster_status("demo")
    assert status.exists is True
    assert status.ready is False
    assert status.nodes == ("demo-control-plane",)
    assert status.message and "connection refused" in status.message


def test_apply_parses_multiple_resources(tmp_path: Path) -> None:
    """``kubectl apply`` stdout with several lines parses to several refs."""
    manifest = tmp_path / "bundle.yaml"
    manifest.write_text("noop")

    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(stdout=(
            "namespace/demo created\n"
            "service/demo unchanged\n"
            "deployment.apps/demo configured\n"
        ))

    runtime = KindClusterRuntime(subprocess_runner=runner)
    result = runtime.apply(SimpleNamespace(name="demo"), manifest)
    assert result.success is True
    assert set(result.applied) == {
        "namespace/demo",
        "service/demo",
        "deployment.apps/demo",
    }


def test_get_returns_not_found_on_nonzero() -> None:
    """``kubectl get`` failures map to ``ResourceState(found=False)``."""
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(returncode=1, stderr="NotFound")

    runtime = KindClusterRuntime(subprocess_runner=runner)
    state = runtime.get(
        SimpleNamespace(name="demo"),
        SimpleNamespace(api_version="v1", kind="Pod"),
        "missing",
        namespace=None,
    )
    assert state.found is False
    assert state.name == "missing"
    assert state.kind == "Pod"
    assert state.raw["stderr"] == "NotFound"


def test_events_with_empty_items_returns_empty_list() -> None:
    def runner(argv: list[str], *, timeout_s: float, env: Any = None) -> Any:
        return _completed(stdout=json.dumps({"items": []}))

    runtime = KindClusterRuntime(subprocess_runner=runner)
    assert runtime.events(SimpleNamespace(name="demo")) == []
