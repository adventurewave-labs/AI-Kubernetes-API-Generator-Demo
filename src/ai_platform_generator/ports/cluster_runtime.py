"""``ClusterRuntime`` port and its supporting value objects.

See ``docs/ddd/07-anti-corruption-layers.md`` section 4 for the contract
and subprocess-hygiene rules adapters must respect.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_platform_generator.domain.aggregates import Cluster, ClusterConfig
    from ai_platform_generator.domain.values import GVK


@dataclass(frozen=True, slots=True)
class MissingTool:
    """A tool the runtime expected to find on ``$PATH`` but did not."""

    name: str
    expected_version_range: str | None
    install_hint: str


@dataclass(frozen=True, slots=True)
class ClusterStatus:
    """Snapshot of a cluster's reachability and health."""

    name: str
    exists: bool
    ready: bool
    nodes: tuple[str, ...] = ()
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Outcome of a ``kubectl apply``-style call against the cluster."""

    success: bool
    applied: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class ResourceState:
    """The state of a single Kubernetes resource as observed."""

    name: str
    namespace: str | None
    api_version: str
    kind: str
    found: bool
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResourceDescription:
    """Human-readable ``kubectl describe``-style output for a resource."""

    name: str
    namespace: str | None
    text: str


@dataclass(frozen=True, slots=True)
class ClusterEvent:
    """A Kubernetes ``Event`` reduced to the fields we care about."""

    timestamp: datetime
    type: str  # "Normal" | "Warning"
    reason: str
    message: str
    involved_object: str


@runtime_checkable
class ClusterRuntime(Protocol):
    """Lifecycle of a cluster + apply/get/describe of manifests."""

    name: str  # "kind", "k3d", "external", "fake", ...

    def check_prerequisites(self) -> list[MissingTool]:
        """List the CLI tools we need but cannot find on ``$PATH``."""

    def cluster_status(self, name: str) -> ClusterStatus:
        """Return the current status of the named cluster."""

    def create_cluster(self, name: str, config: ClusterConfig) -> Cluster:
        """Create a new cluster with ``name`` according to ``config``."""

    def delete_cluster(self, name: str) -> None:
        """Delete the named cluster. Idempotent on already-absent clusters."""

    def apply(self, cluster: Cluster, manifest_path: Path) -> ApplyResult:
        """Apply the manifest at ``manifest_path`` against ``cluster``."""

    def get(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceState:
        """Return the observed state of a single resource."""

    def describe(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceDescription:
        """Return ``kubectl describe``-style text for a single resource."""

    def events(self, cluster: Cluster) -> list[ClusterEvent]:
        """Return recent events for the cluster."""
