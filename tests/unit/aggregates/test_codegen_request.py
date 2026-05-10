"""Tests for ``CodegenRequest`` aggregate root."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

import pytest

from ai_platform_generator.domain.aggregates.codegen_request import (
    CodegenRequest,
    InvalidCodegenRequest,
)
from ai_platform_generator.domain.errors import EmptySpec
from ai_platform_generator.domain.values import (
    GVK,
    Group,
    Kind,
    OutputPath,
    PropertyConstraints,
    PropertyType,
    ProviderMode,
    SpecProperty,
    Version,
)

NO_C = PropertyConstraints()


def _gvk() -> GVK:
    return GVK(Group("platform.example.com"), Version("v1"), Kind("Database"))


def _output_path() -> OutputPath:
    return OutputPath(root=Path(mkdtemp()), relative=Path("out"))


def _prop(name: str = "replicas", t: PropertyType = PropertyType.INTEGER) -> SpecProperty:
    return SpecProperty(name=name, type=t, description="d", constraints=NO_C)


def _request(**kwargs: object) -> CodegenRequest:
    defaults = {
        "gvk": _gvk(),
        "spec_properties": (_prop(),),
        "output_path": _output_path(),
        "description": "A request",
        "provider_mode": ProviderMode.LIVE,
    }
    defaults.update(kwargs)
    return CodegenRequest(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_minimal_request_constructs() -> None:
    r = _request()
    assert r.gvk.kind.value == "Database"
    assert len(r.spec_properties) == 1
    assert r.provider_mode is ProviderMode.LIVE


def test_with_provider_mode_returns_new_instance() -> None:
    r = _request()
    r2 = r.with_provider_mode(ProviderMode.DEMO)
    assert r2 is not r
    assert r2.provider_mode is ProviderMode.DEMO
    assert r.provider_mode is ProviderMode.LIVE


def test_with_output_path_returns_new_instance() -> None:
    r = _request()
    new = OutputPath(root=Path(mkdtemp()), relative=Path("other"))
    r2 = r.with_output_path(new)
    assert r2 is not r
    assert r2.output_path == new


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_empty_spec_properties_rejected() -> None:
    with pytest.raises(EmptySpec):
        _request(spec_properties=())


def test_duplicate_spec_property_names_rejected() -> None:
    with pytest.raises(InvalidCodegenRequest):
        _request(
            spec_properties=(
                _prop(name="replicas"),
                _prop(name="replicas"),
            )
        )


def test_blank_description_rejected() -> None:
    with pytest.raises(InvalidCodegenRequest):
        _request(description="   ")


def test_overlong_description_rejected() -> None:
    with pytest.raises(InvalidCodegenRequest):
        _request(description="x" * 1025)


def test_non_tuple_spec_properties_rejected() -> None:
    with pytest.raises(InvalidCodegenRequest):
        _request(spec_properties=[_prop()])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip() -> None:
    r = _request(
        spec_properties=(
            SpecProperty(
                name="port",
                type=PropertyType.INTEGER,
                description="port number",
                constraints=PropertyConstraints(minimum=1, maximum=65535),
            ),
            SpecProperty(
                name="tags",
                type=PropertyType.ARRAY,
                description="tags",
                constraints=NO_C,
                item_type=PropertyType.STRING,
            ),
        )
    )
    data = r.to_dict()
    r2 = CodegenRequest.from_dict(data)
    assert r2 == r


def test_from_dict_rejects_bad_input() -> None:
    with pytest.raises(InvalidCodegenRequest):
        CodegenRequest.from_dict("not a mapping")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Equality / hash (frozen dataclass)
# ---------------------------------------------------------------------------


def test_equal_requests_compare_equal() -> None:
    op = _output_path()
    a = _request(output_path=op)
    b = _request(output_path=op)
    assert a == b
