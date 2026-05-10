"""Unit tests for the Wave-4 :class:`Deployment` shape.

Covers the new fields (``gvk``, ``instance_name``, ``status_text``,
``crd_applied`` / ``instance_applied`` defaults) the verify path of
:class:`ClusterProvisioningService` reads on its argument.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_platform_generator.domain.aggregates.generation_run import (
    Deployment,
    InvalidGenerationRun,
)
from ai_platform_generator.domain.values import GVK, Group, Kind, Version


def _gvk() -> GVK:
    return GVK(
        group=Group("platform.example.com"),
        version=Version("v1alpha1"),
        kind=Kind("Foo"),
    )


def test_deployment_minimum_construction() -> None:
    d = Deployment(id=uuid4(), cluster_name="my-cluster")
    assert d.cluster_name == "my-cluster"
    assert d.gvk is None
    assert d.instance_name == ""
    assert not d.crd_applied
    assert not d.instance_applied
    assert d.verified_at is None
    assert d.status_text is None


def test_deployment_full_shape() -> None:
    g = _gvk()
    now = datetime.now(timezone.utc)
    d = Deployment(
        id=uuid4(),
        cluster_name="my-cluster",
        gvk=g,
        instance_name="my-foo-instance",
        crd_applied=True,
        instance_applied=True,
        verified_at=now,
        status_text="ok",
    )
    assert d.gvk is g
    assert d.instance_name == "my-foo-instance"
    assert d.crd_applied
    assert d.instance_applied
    assert d.verified_at is now
    assert d.status_text == "ok"


def test_deployment_rejects_non_gvk() -> None:
    with pytest.raises(InvalidGenerationRun):
        Deployment(
            id=uuid4(),
            cluster_name="x",
            gvk="not-a-gvk",  # type: ignore[arg-type]
        )


def test_deployment_rejects_non_str_instance_name() -> None:
    with pytest.raises(InvalidGenerationRun):
        Deployment(
            id=uuid4(),
            cluster_name="x",
            instance_name=42,  # type: ignore[arg-type]
        )


def test_deployment_rejects_non_str_status_text() -> None:
    with pytest.raises(InvalidGenerationRun):
        Deployment(
            id=uuid4(),
            cluster_name="x",
            status_text=12345,  # type: ignore[arg-type]
        )


def test_deployment_is_frozen() -> None:
    d = Deployment(id=uuid4(), cluster_name="x")
    with pytest.raises(Exception):
        d.cluster_name = "y"  # type: ignore[misc]
