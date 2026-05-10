"""Tests for ``ai_platform_generator.domain.values.spec_property``.

Covers the (PropertyType x constraints) acceptance/rejection matrix from
``docs/ddd/04-tactical-design.md`` section 2.5.
"""

from __future__ import annotations

import pytest

from ai_platform_generator.domain.errors import InvalidSpecProperty
from ai_platform_generator.domain.values.property_constraints import PropertyConstraints
from ai_platform_generator.domain.values.property_type import PropertyType
from ai_platform_generator.domain.values.spec_property import SpecProperty

NO_C = PropertyConstraints()


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["foo", "fooBar", "fooBar2", "x", "aB"],
)
def test_valid_name_accepts(name: str) -> None:
    SpecProperty(
        name=name,
        type=PropertyType.STRING,
        description="ok",
        constraints=NO_C,
    )


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Foo",  # PascalCase forbidden
        "1foo",
        "foo_bar",
        "foo-bar",
        "foo bar",
        "foo.bar",
    ],
)
def test_invalid_name_rejects(name: str) -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name=name,
            type=PropertyType.STRING,
            description="ok",
            constraints=NO_C,
        )


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("description", ["", "   ", "\t\n"])
def test_empty_description_rejects(description: str) -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name="foo",
            type=PropertyType.STRING,
            description=description,
            constraints=NO_C,
        )


def test_non_empty_description_ok() -> None:
    SpecProperty(
        name="foo",
        type=PropertyType.STRING,
        description="describes the thing",
        constraints=NO_C,
    )


# ---------------------------------------------------------------------------
# (type x item_type) matrix
# ---------------------------------------------------------------------------


SCALAR_TYPES = [
    PropertyType.STRING,
    PropertyType.INTEGER,
    PropertyType.NUMBER,
    PropertyType.BOOLEAN,
]


@pytest.mark.parametrize("t", SCALAR_TYPES)
def test_scalar_without_item_type_ok(t: PropertyType) -> None:
    SpecProperty(name="x", type=t, description="d", constraints=NO_C)


@pytest.mark.parametrize("t", SCALAR_TYPES)
def test_scalar_with_item_type_rejects(t: PropertyType) -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name="x",
            type=t,
            description="d",
            constraints=NO_C,
            item_type=PropertyType.STRING,
        )


@pytest.mark.parametrize("inner", SCALAR_TYPES)
def test_array_of_scalar_ok(inner: PropertyType) -> None:
    SpecProperty(
        name="x",
        type=PropertyType.ARRAY,
        description="d",
        constraints=NO_C,
        item_type=inner,
    )


def test_array_without_item_type_rejects() -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name="x",
            type=PropertyType.ARRAY,
            description="d",
            constraints=NO_C,
        )


@pytest.mark.parametrize("inner", [PropertyType.ARRAY, PropertyType.OBJECT])
def test_array_of_non_scalar_rejects(inner: PropertyType) -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name="x",
            type=PropertyType.ARRAY,
            description="d",
            constraints=NO_C,
            item_type=inner,
        )


def test_object_no_item_type_ok() -> None:
    # OBJECT is accepted as a leaf for v1 (nested schemas out of scope).
    SpecProperty(
        name="x",
        type=PropertyType.OBJECT,
        description="d",
        constraints=NO_C,
    )


def test_object_with_item_type_rejects() -> None:
    with pytest.raises(InvalidSpecProperty):
        SpecProperty(
            name="x",
            type=PropertyType.OBJECT,
            description="d",
            constraints=NO_C,
            item_type=PropertyType.STRING,
        )


# ---------------------------------------------------------------------------
# Frozen / equality
# ---------------------------------------------------------------------------


def test_equality_and_hash() -> None:
    a = SpecProperty(name="x", type=PropertyType.STRING, description="d", constraints=NO_C)
    b = SpecProperty(name="x", type=PropertyType.STRING, description="d", constraints=NO_C)
    c = SpecProperty(name="y", type=PropertyType.STRING, description="d", constraints=NO_C)
    assert a == b
    assert a != c
    assert len({a, b, c}) == 2
