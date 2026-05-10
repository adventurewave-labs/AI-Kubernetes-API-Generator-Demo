"""Tests for :class:`FakeClusterRuntime`."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime
from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterStatus,
    ResourceState,
)


def _gvk_stub(
    group: str = "example.com", version: str = "v1", kind: str = "Widget"
) -> SimpleNamespace:
    return SimpleNamespace(
        api_version=f"{group}/{version}",
        group=group,
        version=version,
        kind=kind,
    )


def test_check_prerequisites_returns_empty() -> None:
    rt = FakeClusterRuntime()
    assert rt.check_prerequisites() == []


def test_full_lifecycle_create_apply_get_delete() -> None:
    rt = FakeClusterRuntime()

    # Status before creation: not present.
    pre = rt.cluster_status("demo")
    assert pre == ClusterStatus(name="demo", exists=False, ready=False)

    cluster = rt.create_cluster("demo", config=SimpleNamespace())
    assert cluster.name == "demo"

    post = rt.cluster_status("demo")
    assert post.exists is True
    assert post.ready is True
    assert post.nodes == ("fake-control-plane",)

    apply_result = rt.apply(cluster, Path("/tmp/manifest.yaml"))
    assert isinstance(apply_result, ApplyResult)
    assert apply_result.success is True
    assert apply_result.applied == ("/tmp/manifest.yaml",)

    state = rt.get(cluster, _gvk_stub(), name="w1", namespace="default")
    assert isinstance(state, ResourceState)
    assert state.found is True
    assert state.name == "w1"
    assert state.namespace == "default"
    assert state.kind == "Widget"

    description = rt.describe(cluster, _gvk_stub(), name="w1", namespace="default")
    assert "w1" in description.text

    rt.delete_cluster("demo")
    assert rt.cluster_status("demo").exists is False


def test_events_returns_injected_entries() -> None:
    rt = FakeClusterRuntime()
    cluster = rt.create_cluster("demo", config=SimpleNamespace())
    ev = rt.add_event("demo")

    assert rt.events(cluster) == [ev]


def test_set_failure_makes_apply_raise() -> None:
    rt = FakeClusterRuntime()
    cluster = rt.create_cluster("demo", config=SimpleNamespace())

    boom = RuntimeError("simulated kubectl exit 1")
    rt.set_failure("apply", boom)

    with pytest.raises(RuntimeError, match="simulated"):
        rt.apply(cluster, Path("/tmp/m.yaml"))

    rt.clear_failure("apply")
    # After clearing, apply succeeds again.
    assert rt.apply(cluster, Path("/tmp/m.yaml")).success is True


def test_set_failure_can_target_create_cluster() -> None:
    rt = FakeClusterRuntime()
    rt.set_failure("create_cluster", RuntimeError("missing kind"))

    with pytest.raises(RuntimeError, match="missing kind"):
        rt.create_cluster("demo", config=SimpleNamespace())


def test_calls_log_records_invocations() -> None:
    rt = FakeClusterRuntime()
    rt.check_prerequisites()
    rt.cluster_status("absent")

    assert ("check_prerequisites", ()) in rt.calls
    assert ("cluster_status", ("absent",)) in rt.calls
