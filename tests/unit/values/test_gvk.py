"""Tests for ``ai_platform_generator.domain.values.gvk``."""

from __future__ import annotations

import pytest

from ai_platform_generator.domain.values.group import Group
from ai_platform_generator.domain.values.gvk import GVK
from ai_platform_generator.domain.values.kind import Kind
from ai_platform_generator.domain.values.version import Version


@pytest.fixture
def gvk() -> GVK:
    return GVK(
        group=Group("database.example.com"),
        version=Version("v1alpha1"),
        kind=Kind("PostgresCluster"),
    )


def test_crd_name(gvk: GVK) -> None:
    assert gvk.crd_name == "postgresclusters.database.example.com"


def test_api_version(gvk: GVK) -> None:
    assert gvk.api_version == "database.example.com/v1alpha1"


def test_equality_and_hash(gvk: GVK) -> None:
    same = GVK(
        group=Group("database.example.com"),
        version=Version("v1alpha1"),
        kind=Kind("PostgresCluster"),
    )
    other = GVK(
        group=Group("database.example.com"),
        version=Version("v1"),
        kind=Kind("PostgresCluster"),
    )
    assert gvk == same
    assert gvk != other
    assert len({gvk, same, other}) == 2


def test_pluralisation_branches() -> None:
    cases = [
        ("Bus", "buses"),
        ("Policy", "policies"),
        ("Database", "databases"),
    ]
    for kind, plural in cases:
        g = GVK(
            group=Group("a.b"),
            version=Version("v1"),
            kind=Kind(kind),
        )
        assert g.crd_name == f"{plural}.a.b"
        assert g.api_version == "a.b/v1"
