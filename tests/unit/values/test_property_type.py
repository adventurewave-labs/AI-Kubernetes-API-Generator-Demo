"""Tests for ``ai_platform_generator.domain.values.property_type``."""

from __future__ import annotations

from ai_platform_generator.domain.values.property_type import PropertyType


def test_string_values_match_jsonschema() -> None:
    assert PropertyType.STRING.value == "string"
    assert PropertyType.INTEGER.value == "integer"
    assert PropertyType.NUMBER.value == "number"
    assert PropertyType.BOOLEAN.value == "boolean"
    assert PropertyType.ARRAY.value == "array"
    assert PropertyType.OBJECT.value == "object"


def test_strenum_str_compat() -> None:
    # StrEnum values compare equal to their str form.
    assert PropertyType.STRING == "string"
    assert "integer" == PropertyType.INTEGER


def test_iteration_complete() -> None:
    names = {pt.name for pt in PropertyType}
    assert names == {"STRING", "INTEGER", "NUMBER", "BOOLEAN", "ARRAY", "OBJECT"}
