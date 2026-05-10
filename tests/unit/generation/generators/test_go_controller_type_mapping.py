"""Parametrised tests for the IR → Go type mapping table.

Covers every ``PropertyType`` x ``item_type`` combination plus the
required-vs-optional pointer behaviour. The table is the single source
of truth for both the templates and downstream golden tests; a
regression in either direction breaks loud here.
"""

from __future__ import annotations

import pytest

from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.generators.go_controller import (
    _go_type_for,
    _scalar_go_type,
)


# ----------------------------------------------------------------------
# Scalar mapping
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("json_type", "expected"),
    [
        ("string", "string"),
        ("integer", "int32"),
        ("number", "float64"),
        ("boolean", "bool"),
    ],
)
def test_scalar_required_is_value_type(json_type: str, expected: str) -> None:
    assert _go_type_for(json_type, required=True) == expected
    assert _scalar_go_type(json_type) == expected


@pytest.mark.parametrize(
    ("json_type", "expected"),
    [
        ("string", "*string"),
        ("integer", "*int32"),
        ("number", "*float64"),
        ("boolean", "*bool"),
    ],
)
def test_scalar_optional_is_pointer(json_type: str, expected: str) -> None:
    assert _go_type_for(json_type, required=False) == expected


# ----------------------------------------------------------------------
# Array mapping (every supported element type)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("item_type", "expected"),
    [
        ("string", "[]string"),
        ("integer", "[]int32"),
        ("number", "[]float64"),
        ("boolean", "[]bool"),
    ],
)
@pytest.mark.parametrize("required", [True, False])
def test_array_mapping(item_type: str, expected: str, required: bool) -> None:
    # Arrays are not pointer-wrapped — nil slice already encodes "unset".
    assert _go_type_for("array", item_type=item_type, required=required) == expected


def test_array_without_item_type_is_an_error() -> None:
    with pytest.raises(ArtifactGenerationError, match="missing item_type"):
        _go_type_for("array")


# ----------------------------------------------------------------------
# Object mapping — placeholder per v1 limitation
# ----------------------------------------------------------------------
@pytest.mark.parametrize("required", [True, False])
def test_object_mapping_is_map_string_string(required: bool) -> None:
    assert _go_type_for("object", required=required) == "map[string]string"


# ----------------------------------------------------------------------
# Unknown type → typed error
# ----------------------------------------------------------------------
def test_unknown_scalar_raises_artifact_generation_error() -> None:
    with pytest.raises(ArtifactGenerationError, match="unsupported scalar"):
        _scalar_go_type("nonexistent")


def test_unknown_type_raises_via_go_type_for() -> None:
    with pytest.raises(ArtifactGenerationError, match="unsupported scalar"):
        _go_type_for("nonexistent")
