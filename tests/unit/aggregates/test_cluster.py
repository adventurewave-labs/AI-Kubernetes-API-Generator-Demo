"""Unit tests for the :class:`Cluster` / :class:`ClusterConfig` aggregates."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_platform_generator.domain.aggregates.cluster import (
    Cluster,
    ClusterConfig,
    InvalidCluster,
)
from ai_platform_generator.ports.cluster_runtime import ClusterStatus

# ---------------------------------------------------------------------------
# ClusterConfig
# ---------------------------------------------------------------------------


def test_cluster_config_defaults() -> None:
    cfg = ClusterConfig(name="my-cluster")
    assert cfg.runtime == "kind"
    assert cfg.node_count == 1
    assert cfg.port_mappings == ((80, 80), (443, 443))


def test_cluster_config_rejects_invalid_dns_1123_name() -> None:
    bad_names = [
        "Cluster",       # uppercase
        "1bad",          # leading digit
        "-dash",         # leading dash
        "trail-",        # trailing dash
        "my_cluster",    # underscore
        "",              # empty
        " spaces ",      # whitespace
        "x" * 64,        # too long (> 63 chars)
    ]
    for name in bad_names:
        with pytest.raises(InvalidCluster):
            ClusterConfig(name=name)


def test_cluster_config_accepts_valid_dns_1123_names() -> None:
    for name in ("c", "ai-platform-demo", "a1b2c3", "x" * 63):
        ClusterConfig(name=name)  # must not raise


def test_cluster_config_rejects_invalid_node_count() -> None:
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", node_count=0)
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", node_count=-1)
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", node_count=True)  # type: ignore[arg-type]


def test_cluster_config_rejects_invalid_port_mapping() -> None:
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", port_mappings=((80, 70000),))
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", port_mappings=((0, 80),))
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", port_mappings=((80,),))  # type: ignore[arg-type]
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", port_mappings="80,80")  # type: ignore[arg-type]


def test_cluster_config_rejects_blank_runtime() -> None:
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", runtime="")
    with pytest.raises(InvalidCluster):
        ClusterConfig(name="x", runtime="   ")


def test_cluster_config_is_frozen(tmp_path: Path) -> None:
    cfg = ClusterConfig(name="x")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        cfg.name = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------


def _config(name: str = "my-cluster") -> ClusterConfig:
    return ClusterConfig(name=name)


def test_cluster_constructs_with_minimum_fields(tmp_path: Path) -> None:
    cluster = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kubeconfig",
    )
    assert cluster.name == "my-cluster"
    assert cluster.nodes == ()
    assert cluster.status is None


def test_cluster_name_must_match_config_name(tmp_path: Path) -> None:
    with pytest.raises(InvalidCluster):
        Cluster(
            name="mismatch",
            config=_config("my-cluster"),
            kubeconfig_path=tmp_path / "kc",
        )


def test_cluster_rejects_invalid_dns_1123_name(tmp_path: Path) -> None:
    with pytest.raises(InvalidCluster):
        Cluster(
            name="Bad",
            config=ClusterConfig(name="Bad"),  # ClusterConfig also rejects this
            kubeconfig_path=tmp_path / "kc",
        )


def test_cluster_rejects_string_kubeconfig_path() -> None:
    with pytest.raises(InvalidCluster):
        Cluster(
            name="my-cluster",
            config=_config(),
            kubeconfig_path="/tmp/kc",  # type: ignore[arg-type]
        )


def test_cluster_with_nodes_returns_new_instance(tmp_path: Path) -> None:
    cluster = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kc",
    )
    updated = cluster.with_nodes(("node-a", "node-b"))
    assert cluster.nodes == ()
    assert updated.nodes == ("node-a", "node-b")
    assert updated is not cluster


def test_cluster_with_nodes_accepts_iterable(tmp_path: Path) -> None:
    cluster = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kc",
    )
    updated = cluster.with_nodes(["a", "b"])  # type: ignore[arg-type]
    assert updated.nodes == ("a", "b")


def test_cluster_with_status_returns_new_instance(tmp_path: Path) -> None:
    cluster = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kc",
    )
    status = ClusterStatus(name="my-cluster", exists=True, ready=True)
    updated = cluster.with_status(status)
    assert cluster.status is None
    assert updated.status is status


def test_cluster_equality_is_identity_based(tmp_path: Path) -> None:
    a = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kc-a",
    )
    b = Cluster(
        name="my-cluster",
        config=_config(),
        kubeconfig_path=tmp_path / "kc-b",
        nodes=("node-1",),
    )
    c = Cluster(
        name="other-cluster",
        config=_config("other-cluster"),
        kubeconfig_path=tmp_path / "kc-c",
    )

    assert a == b  # same name, regardless of nodes / kubeconfig
    assert hash(a) == hash(b)
    assert a != c
