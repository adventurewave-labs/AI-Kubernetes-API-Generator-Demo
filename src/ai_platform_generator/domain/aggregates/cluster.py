"""``Cluster`` aggregate (root: ``Cluster`` entity).

Realises ``docs/ddd/04-tactical-design.md`` §3.2 and §4.4.

The ``Cluster`` aggregate is owned by the *Cluster Provisioning* bounded
context (see ``docs/ddd/bounded-contexts/04-cluster-provisioning.md``).
The aggregate root is a small mutable entity identified by its
``name`` — Kubernetes treats the cluster name as identity, so we mirror
that. The constructor validates the DNS-1123 invariant on the name and
delegates the rest of the configuration to the immutable
:class:`ClusterConfig` value object.

Mutation is only possible through the named builders
(:meth:`Cluster.with_nodes` / :meth:`Cluster.with_status`); both return
a *new* instance so the aggregate is effectively functional in the
common case.

Inputs are validated up-front; downstream code can rely on every
``Cluster`` instance being well-formed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from ai_platform_generator.domain.errors.domain_validation import (
    DomainValidationError,
)
from ai_platform_generator.ports.cluster_runtime import ClusterStatus

#: DNS-1123 label pattern — ``kind`` cluster names must satisfy this.
#: Same pattern Kubernetes itself uses for resource ``metadata.name``.
_DNS_1123_LABEL = re.compile(r"^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$")


class InvalidCluster(DomainValidationError):
    """Raised when a :class:`Cluster` or :class:`ClusterConfig` invariant fails."""

    code = "E_DOMAIN_INVALID_CLUSTER"


def _validate_dns_1123_name(name: str, *, field: str = "name") -> None:
    if not isinstance(name, str):
        raise InvalidCluster(
            f"{field} must be a str, got {type(name).__name__}"
        )
    if not _DNS_1123_LABEL.fullmatch(name):
        raise InvalidCluster(
            f"{field} {name!r} is not a valid DNS-1123 label "
            f"(pattern: {_DNS_1123_LABEL.pattern})"
        )


# ---------------------------------------------------------------------------
# ClusterConfig (immutable value object)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClusterConfig:
    """Configuration for a managed cluster.

    Frozen value object — modifications produce a new instance via
    :func:`dataclasses.replace`.
    """

    name: str
    runtime: str = "kind"
    node_count: int = 1
    port_mappings: tuple[tuple[int, int], ...] = ((80, 80), (443, 443))

    def __post_init__(self) -> None:
        _validate_dns_1123_name(self.name)

        if not isinstance(self.runtime, str) or not self.runtime.strip():
            raise InvalidCluster(
                f"runtime must be a non-blank str, got {self.runtime!r}"
            )

        if not isinstance(self.node_count, int) or isinstance(self.node_count, bool):
            raise InvalidCluster(
                f"node_count must be an int, got {type(self.node_count).__name__}"
            )
        if self.node_count < 1:
            raise InvalidCluster(
                f"node_count must be >= 1, got {self.node_count}"
            )

        if not isinstance(self.port_mappings, tuple):
            raise InvalidCluster(
                "port_mappings must be a tuple of (host, container) pairs"
            )
        for entry in self.port_mappings:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or not all(isinstance(p, int) and not isinstance(p, bool) for p in entry)
            ):
                raise InvalidCluster(
                    f"port_mappings entries must be (int, int) tuples, got {entry!r}"
                )
            host, container = entry
            for label, port in (("host", host), ("container", container)):
                if not 1 <= port <= 65535:
                    raise InvalidCluster(
                        f"port_mappings {label} port {port} is out of range (1..65535)"
                    )


# ---------------------------------------------------------------------------
# Cluster (mutable entity)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Cluster:
    """The Cluster Provisioning aggregate root.

    Identity is :attr:`name`. The remaining fields evolve as the cluster
    is created and observed; mutation is performed through
    :meth:`with_nodes` and :meth:`with_status`, which return a new
    instance, leaving the original untouched.
    """

    name: str
    config: ClusterConfig
    kubeconfig_path: Path
    nodes: tuple[str, ...] = ()
    status: ClusterStatus | None = None

    def __post_init__(self) -> None:
        _validate_dns_1123_name(self.name)

        if not isinstance(self.config, ClusterConfig):
            raise InvalidCluster(
                f"config must be a ClusterConfig, got {type(self.config).__name__}"
            )
        if self.config.name != self.name:
            raise InvalidCluster(
                "Cluster.name and Cluster.config.name must match "
                f"(got {self.name!r} vs {self.config.name!r})"
            )

        if not isinstance(self.kubeconfig_path, Path):
            raise InvalidCluster(
                "kubeconfig_path must be a pathlib.Path, got "
                f"{type(self.kubeconfig_path).__name__}"
            )

        if not isinstance(self.nodes, tuple) or any(
            not isinstance(n, str) for n in self.nodes
        ):
            raise InvalidCluster(
                "nodes must be a tuple of str, got "
                f"{self.nodes!r}"
            )

        if self.status is not None and not isinstance(self.status, ClusterStatus):
            raise InvalidCluster(
                "status must be a ClusterStatus or None, got "
                f"{type(self.status).__name__}"
            )

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def with_nodes(self, nodes: tuple[str, ...]) -> Cluster:
        """Return a new :class:`Cluster` with ``nodes`` replaced."""
        if not isinstance(nodes, tuple):
            nodes = tuple(nodes)
        return replace(self, nodes=nodes)

    def with_status(self, status: ClusterStatus) -> Cluster:
        """Return a new :class:`Cluster` with ``status`` replaced."""
        return replace(self, status=status)

    # ------------------------------------------------------------------
    # Identity-based equality (entity semantics)
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cluster):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


__all__ = [
    "Cluster",
    "ClusterConfig",
    "InvalidCluster",
]
