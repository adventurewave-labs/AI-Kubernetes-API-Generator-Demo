"""Tests for the :class:`GenerationPlan` value object."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from ai_platform_generator.domain.aggregates import ArtifactType
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan


def _plan(**overrides: object) -> GenerationPlan:
    base: dict[str, object] = {
        "generator_name": "crd",
        "artefact_type": ArtifactType.CRD,
        "target_files": (Path("/tmp/x/postgres.crd.yaml"),),
        "metadata": {"kind": "Postgres"},
    }
    base.update(overrides)
    return GenerationPlan(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------
def test_plan_constructs_with_minimum_args() -> None:
    p = GenerationPlan(
        generator_name="openapi",
        artefact_type=ArtifactType.OPENAPI,
        target_files=(Path("/out/openapi.json"),),
    )
    assert p.generator_name == "openapi"
    assert p.target_files == (Path("/out/openapi.json"),)
    # Default metadata is read-only and empty.
    assert dict(p.metadata) == {}


def test_plan_rejects_blank_generator_name() -> None:
    with pytest.raises(ValueError, match="generator_name must be a non-empty str"):
        _plan(generator_name="")


def test_plan_rejects_non_str_generator_name() -> None:
    with pytest.raises(ValueError, match="generator_name must be a non-empty str"):
        _plan(generator_name=123)


def test_plan_rejects_non_tuple_target_files() -> None:
    with pytest.raises(TypeError, match="target_files must be a tuple"):
        _plan(target_files=[Path("/x")])


def test_plan_rejects_non_path_in_target_files() -> None:
    with pytest.raises(TypeError, match="target_files entry must be a Path"):
        _plan(target_files=("/not/a/Path",))


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------
def test_plan_is_frozen() -> None:
    p = _plan()
    with pytest.raises(FrozenInstanceError):
        p.generator_name = "other"  # type: ignore[misc]


def test_plan_metadata_wrapped_in_mapping_proxy() -> None:
    p = _plan(metadata={"a": 1})
    # We get back a read-only view, not the original dict.
    assert isinstance(p.metadata, MappingProxyType)
    assert p.metadata["a"] == 1


def test_plan_metadata_wrap_breaks_aliasing() -> None:
    """Mutating the dict passed in must not leak through into ``plan.metadata``."""
    src = {"k": "v1"}
    p = _plan(metadata=src)
    src["k"] = "v2"
    assert p.metadata["k"] == "v1"


# ---------------------------------------------------------------------------
# Equality
# ---------------------------------------------------------------------------
def test_plan_equality_is_value_based() -> None:
    a = _plan()
    b = _plan()
    assert a == b
    # Note: not asserting hash equality — ``metadata`` is wrapped in a
    # ``MappingProxyType`` which is intentionally non-hashable. Equality
    # by-value is the load-bearing invariant for a value object.


def test_plan_equality_distinguishes_paths() -> None:
    a = _plan()
    b = _plan(target_files=(Path("/tmp/x/other.crd.yaml"),))
    assert a != b
