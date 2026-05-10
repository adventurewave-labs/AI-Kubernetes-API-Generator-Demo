"""Tests for :class:`FieldViolation`.

It is a tiny frozen dataclass; the tests pin its semantics so changing
its shape requires an explicit edit (the type is part of ADR-0016's
public contract).
"""
from __future__ import annotations

import dataclasses

import pytest

from ai_platform_generator.domain.errors import FieldViolation


def test_construction_requires_all_fields() -> None:
    fv = FieldViolation(
        path="spec_properties.replicas.type",
        expected="int",
        actual="str",
        message="replicas.type must be 'integer', not 'string'",
    )
    assert fv.path == "spec_properties.replicas.type"
    assert fv.expected == "int"
    assert fv.actual == "str"
    assert "replicas.type" in fv.message


def test_is_frozen() -> None:
    fv = FieldViolation(path="a", expected="b", actual="c", message="d")
    with pytest.raises(dataclasses.FrozenInstanceError):
        fv.path = "z"  # type: ignore[misc]


def test_value_equality() -> None:
    a = FieldViolation(path="p", expected="e", actual="a", message="m")
    b = FieldViolation(path="p", expected="e", actual="a", message="m")
    c = FieldViolation(path="p", expected="e", actual="a", message="X")
    assert a == b
    assert a != c
    # Hashable because frozen + immutable fields.
    assert {a, b} == {a}
