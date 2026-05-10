"""Unit tests for :class:`ClusterProvisioningService`."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime
from ai_platform_generator.application.services.cluster_provisioning import (
    ClusterProvisioningService,
)
from ai_platform_generator.domain.errors import (
    ClusterCreationTimedOut,
    DeploymentVerificationFailed,
    PrerequisiteMissing,
)
from ai_platform_generator.domain.values import GVK, Group, Kind, Version
from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterStatus,
    MissingTool,
    ResourceState,
)


def _service(
    runtime: Any, sink: Any, clock: Any, *, sleep: Any = lambda _s: None
) -> ClusterProvisioningService:
    return ClusterProvisioningService(
        runtime=runtime, events=sink, clock=clock, sleep=sleep
    )


def _gvk() -> GVK:
    return GVK(
        group=Group("platform.example.com"),
        version=Version("v1alpha1"),
        kind=Kind("Foo"),
    )


def _bundle(crd_path: Path, inst_path: Path) -> Any:
    """Minimal stand-in bundle with the two artefacts the service expects."""
    request = SimpleNamespace(gvk=_gvk())
    manifest = SimpleNamespace(request=request)
    file_crd = SimpleNamespace(
        path=crd_path,
        artefact_type=SimpleNamespace(value="crd"),
    )
    file_inst = SimpleNamespace(
        path=inst_path,
        artefact_type=SimpleNamespace(value="instance"),
    )
    return SimpleNamespace(
        manifest=manifest, files=(file_crd, file_inst)
    )


# ---------------------------------------------------------------------------
# check_prerequisites
# ---------------------------------------------------------------------------


def test_check_prerequisites_passes_when_runtime_returns_empty(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    svc = _service(runtime, sink, clock)
    svc.check_prerequisites()

    assert sink.events_with_name("PrerequisiteCheckSucceeded")


def test_check_prerequisites_raises_on_missing_tools(sink, clock) -> None:
    class _Rt(FakeClusterRuntime):
        def check_prerequisites(self) -> list[MissingTool]:
            return [
                MissingTool(
                    name="kind",
                    expected_version_range=">=0.20",
                    install_hint="https://kind.sigs.k8s.io/",
                )
            ]

    svc = _service(_Rt(), sink, clock)
    with pytest.raises(PrerequisiteMissing):
        svc.check_prerequisites()
    assert sink.events_with_name("PrerequisiteCheckFailed")


# ---------------------------------------------------------------------------
# ensure
# ---------------------------------------------------------------------------


def test_ensure_creates_cluster_when_absent(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    svc = _service(runtime, sink, clock)
    cluster = svc.ensure("my-cluster")

    assert cluster.name == "my-cluster"
    sink.assert_events_in_order(
        "ClusterCreationStarted", "ClusterCreationSucceeded"
    )


def test_ensure_skips_creation_when_cluster_already_ready(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    runtime._statuses["my-cluster"] = ClusterStatus(
        name="my-cluster", exists=True, ready=True, nodes=("control-plane",)
    )
    svc = _service(runtime, sink, clock)
    svc.ensure("my-cluster")

    assert not sink.events_with_name("ClusterCreationStarted")


def test_ensure_emits_failure_event_and_raises(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    runtime.set_failure(
        "create_cluster",
        ClusterCreationTimedOut("create timed out"),
    )
    svc = _service(runtime, sink, clock)

    with pytest.raises(ClusterCreationTimedOut):
        svc.ensure("my-cluster")
    assert sink.events_with_name("ClusterCreationFailed")


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------


def test_deploy_applies_crd_then_instance_and_emits_events(
    sink, clock, tmp_path
) -> None:
    runtime = FakeClusterRuntime()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )
    svc = _service(runtime, sink, clock)
    bundle = _bundle(tmp_path / "foo.crd.yaml", tmp_path / "foo.instance.yaml")

    deployment = svc.deploy(bundle, cluster)

    assert deployment.cluster_name == "my-cluster"
    sink.assert_events_in_order("CrdApplied", "InstanceApplied")


def test_deploy_raises_when_crd_apply_fails(sink, clock, tmp_path) -> None:
    runtime = FakeClusterRuntime()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )

    class _Rt(FakeClusterRuntime):
        def apply(self, *args: Any, **kw: Any) -> ApplyResult:
            return ApplyResult(success=False, stderr="oh no")

    runtime = _Rt()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )
    svc = _service(runtime, sink, clock)
    bundle = _bundle(tmp_path / "foo.crd.yaml", tmp_path / "foo.instance.yaml")

    with pytest.raises(DeploymentVerificationFailed):
        svc.deploy(bundle, cluster)


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def test_verify_emits_event_when_resource_found(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )
    svc = _service(runtime, sink, clock)

    deployment = SimpleNamespace(
        gvk=_gvk(), instance_name="my-foo-instance", cluster_name="my-cluster"
    )
    svc.verify(deployment, cluster)
    assert sink.events_with_name("DeploymentVerified")


def test_verify_raises_when_resource_not_found(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )

    class _Rt(FakeClusterRuntime):
        def get(self, *args: Any, **kw: Any) -> ResourceState:
            return ResourceState(
                name="x",
                namespace=None,
                api_version="v1",
                kind="Foo",
                found=False,
            )

    runtime = _Rt()
    cluster = runtime.create_cluster(
        "my-cluster", SimpleNamespace(name="my-cluster")
    )
    svc = _service(runtime, sink, clock)
    deployment = SimpleNamespace(
        gvk=_gvk(), instance_name="my-foo-instance", cluster_name="my-cluster"
    )
    with pytest.raises(DeploymentVerificationFailed):
        svc.verify(deployment, cluster)
    assert sink.events_with_name("DeploymentVerificationFailed")


# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------


def test_teardown_delegates_to_runtime(sink, clock) -> None:
    runtime = FakeClusterRuntime()
    runtime.create_cluster("my-cluster", SimpleNamespace(name="my-cluster"))
    svc = _service(runtime, sink, clock)
    svc.teardown("my-cluster")
    # FakeClusterRuntime records the call.
    assert any(c[0] == "delete_cluster" for c in runtime.calls)
