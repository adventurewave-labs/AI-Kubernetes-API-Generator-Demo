"""Deterministic in-memory ``ClusterRuntime`` for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 4.2.

The fake tracks cluster lifecycle and apply/get calls in plain dicts so
unit tests can assert on them without a real container runtime. A
``set_failure(operation, exc)`` hook lets tests simulate adapter
failures (e.g. ``apply`` raising a translated ``ClusterProvisioningError``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterEvent,
    ClusterStatus,
    MissingTool,
    ResourceDescription,
    ResourceState,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import Cluster, ClusterConfig
    from ai_platform_generator.domain.values import GVK


class FakeClusterRuntime:
    """In-memory ``ClusterRuntime`` with injectable failures.

    State is intentionally simple: a dict of clusters keyed by name and a
    list of recorded operations so tests can assert ordering. The
    failure-injection map is consulted at the start of each method so
    tests can simulate a non-zero kubectl exit, a missing ``kind`` CLI,
    etc.
    """

    name: str = "fake"

    def __init__(self) -> None:
        self._clusters: dict[str, Any] = {}
        self._statuses: dict[str, ClusterStatus] = {}
        self._events: dict[str, list[ClusterEvent]] = {}
        self._failures: dict[str, Exception] = {}
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    # ----- failure injection -------------------------------------------

    def set_failure(self, operation: str, exc: Exception) -> None:
        """Cause the named ``operation`` to raise ``exc`` on next call.

        ``operation`` matches the public method name (e.g. ``"apply"``,
        ``"create_cluster"``). The injected failure persists until
        explicitly cleared by ``clear_failure``.
        """
        self._failures[operation] = exc

    def clear_failure(self, operation: str) -> None:
        self._failures.pop(operation, None)

    def _maybe_raise(self, operation: str) -> None:
        exc = self._failures.get(operation)
        if exc is not None:
            raise exc

    # ----- ClusterRuntime protocol -------------------------------------

    def check_prerequisites(self) -> list[MissingTool]:
        self._maybe_raise("check_prerequisites")
        self.calls.append(("check_prerequisites", ()))
        return []

    def cluster_status(self, name: str) -> ClusterStatus:
        self._maybe_raise("cluster_status")
        self.calls.append(("cluster_status", (name,)))
        if name in self._statuses:
            return self._statuses[name]
        return ClusterStatus(name=name, exists=False, ready=False)

    def create_cluster(self, name: str, config: ClusterConfig) -> Cluster:
        self._maybe_raise("create_cluster")
        self.calls.append(("create_cluster", (name, config)))
        # We don't have a real ``Cluster`` aggregate yet (Phase 3+), so
        # we fabricate a tiny stand-in object. Tests that exercise the
        # whole stack will pass an actual aggregate; tests that only
        # exercise this adapter just compare attributes.
        cluster = _FakeCluster(name=name, runtime=self.name)
        self._clusters[name] = cluster
        self._statuses[name] = ClusterStatus(
            name=name, exists=True, ready=True, nodes=("fake-control-plane",),
        )
        self._events.setdefault(name, [])
        # ``_FakeCluster`` is the structural stand-in matched by ``_RealCluster``
        # in the kind adapter; the application service only reads ``.name``.
        return cast("Cluster", cluster)

    def delete_cluster(self, name: str) -> None:
        self._maybe_raise("delete_cluster")
        self.calls.append(("delete_cluster", (name,)))
        self._clusters.pop(name, None)
        self._statuses.pop(name, None)
        self._events.pop(name, None)

    def apply(self, cluster: Cluster, manifest_path: Path) -> ApplyResult:
        self._maybe_raise("apply")
        self.calls.append(("apply", (cluster, manifest_path)))
        return ApplyResult(
            success=True,
            applied=(str(manifest_path),),
            stdout=f"applied {manifest_path}",
            stderr="",
        )

    def get(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceState:
        self._maybe_raise("get")
        self.calls.append(("get", (cluster, gvk, name, namespace)))
        return ResourceState(
            name=name,
            namespace=namespace,
            api_version=getattr(gvk, "api_version", "v1"),
            kind=str(getattr(gvk, "kind", "Unknown")),
            found=True,
            raw={"metadata": {"name": name, "namespace": namespace}},
        )

    def describe(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceDescription:
        self._maybe_raise("describe")
        self.calls.append(("describe", (cluster, gvk, name, namespace)))
        return ResourceDescription(
            name=name,
            namespace=namespace,
            text=f"Name: {name}\nNamespace: {namespace}\n(kind: {getattr(gvk, 'kind', '?')})",
        )

    def events(self, cluster: Cluster) -> list[ClusterEvent]:
        self._maybe_raise("events")
        self.calls.append(("events", (cluster,)))
        cluster_name: str | None = getattr(cluster, "name", None)
        if cluster_name is None:
            return []
        return list(self._events.get(cluster_name, []))

    # ----- test-only sugar ---------------------------------------------

    def add_event(self, cluster_name: str, event: ClusterEvent | None = None) -> ClusterEvent:
        """Append a synthetic cluster event for later retrieval via :meth:`events`."""
        ev = event or ClusterEvent(
            timestamp=datetime.now(UTC),
            type="Normal",
            reason="Synthesized",
            message="injected by FakeClusterRuntime",
            involved_object=cluster_name,
        )
        self._events.setdefault(cluster_name, []).append(ev)
        return ev


class _FakeCluster:
    """Tiny stand-in for the eventual ``Cluster`` aggregate.

    Only used while Phase 3 has not yet landed the real aggregate. Once
    ``ai_platform_generator.domain.aggregates.Cluster`` exists this class
    becomes irrelevant — :meth:`FakeClusterRuntime.create_cluster` will
    accept and return the real type.
    """

    __slots__ = ("name", "runtime")

    def __init__(self, name: str, runtime: str) -> None:
        self.name = name
        self.runtime = runtime

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"_FakeCluster(name={self.name!r}, runtime={self.runtime!r})"
