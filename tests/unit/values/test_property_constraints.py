"""Tests for ``ai_platform_generator.domain.values.property_constraints``."""

from __future__ import annotations

import pytest

from ai_platform_generator.domain.errors import InvalidPropertyConstraints
from ai_platform_generator.domain.values.property_constraints import PropertyConstraints


def test_default_no_constraints() -> None:
    pc = PropertyConstraints()
    assert pc.minimum is None
    assert pc.maximum is None
    assert pc.min_length is None
    assert pc.max_length is None
    assert pc.pattern is None
    assert pc.enum is None
    assert pc.format is None


def test_min_le_max_int_ok() -> None:
    PropertyConstraints(minimum=0, maximum=10)
    PropertyConstraints(minimum=5, maximum=5)


def test_min_le_max_float_ok() -> None:
    PropertyConstraints(minimum=0.5, maximum=1.5)


def test_min_gt_max_rejects() -> None:
    with pytest.raises(InvalidPropertyConstraints):
        PropertyConstraints(minimum=10, maximum=5)


def test_min_only_ok() -> None:
    PropertyConstraints(minimum=0)


def test_max_only_ok() -> None:
    PropertyConstraints(maximum=10)


def test_min_length_le_max_length_ok() -> None:
    PropertyConstraints(min_length=0, max_length=64)


def test_min_length_gt_max_length_rejects() -> None:
    with pytest.raises(InvalidPropertyConstraints):
        PropertyConstraints(min_length=10, max_length=5)


def test_negative_min_length_rejects() -> None:
    with pytest.raises(InvalidPropertyConstraints):
        PropertyConstraints(min_length=-1)


def test_negative_max_length_rejects() -> None:
    with pytest.raises(InvalidPropertyConstraints):
        PropertyConstraints(max_length=-1)


def test_empty_enum_rejects() -> None:
    with pytest.raises(InvalidPropertyConstraints):
        PropertyConstraints(enum=())


def test_non_empty_enum_ok() -> None:
    PropertyConstraints(enum=("a", "b", "c"))


def test_pattern_and_format_arbitrary_strings_ok() -> None:
    pc = PropertyConstraints(pattern="^a.*$", format="email")
    assert pc.pattern == "^a.*$"
    assert pc.format == "email"


def test_frozen_and_hashable() -> None:
    a = PropertyConstraints(minimum=0, maximum=10)
    b = PropertyConstraints(minimum=0, maximum=10)
    assert a == b
    assert hash(a) == hash(b)
    with pytest.raises((AttributeError, TypeError)):
        a.minimum = 1  # type: ignore[misc]
