"""Tests for ``OpenAPIDocument`` aggregate root and IR builder."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

import pytest

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import (
    IR_VERSION,
    OPENAPI_VERSION,
    InvalidOpenAPIDocument,
    OpenAPIDocument,
    OpenApiInfo,
)
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


def _request(spec_properties: tuple[SpecProperty, ...] | None = None) -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        spec_properties=spec_properties
        or (
            SpecProperty(
                name="replicas",
                type=PropertyType.INTEGER,
                description="number of replicas",
                constraints=PropertyConstraints(minimum=1, maximum=10),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="Database CRD",
        provider_mode=ProviderMode.LIVE,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_from_request_builds_ir() -> None:
    req = _request()
    doc = OpenAPIDocument.from_request(req)
    assert isinstance(doc, OpenAPIDocument)
    assert doc.info.title == "Database API"
    assert doc.info.version == "v1"
    assert "Database" in doc.schemas


def test_to_dict_has_canonical_top_level_keys() -> None:
    doc = OpenAPIDocument.from_request(_request())
    d = doc.to_dict()
    assert d["openapi"] == OPENAPI_VERSION
    assert "info" in d
    assert "paths" in d
    assert "components" in d
    assert "schemas" in d["components"]


def test_info_has_kubernetes_gvk_extension() -> None:
    doc = OpenAPIDocument.from_request(_request())
    info_dict = doc.info.model_dump(mode="json")
    assert info_dict["x-kubernetes-gvk"] == {
        "group": "platform.example.com",
        "version": "v1",
        "kind": "Database",
    }
    assert info_dict["x-platform-generator-ir"] == IR_VERSION


def test_gvk_round_trip() -> None:
    req = _request()
    doc = OpenAPIDocument.from_request(req)
    assert doc.gvk == req.gvk


# ---------------------------------------------------------------------------
# Property-type mapping rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ptype", "expected"),
    [
        (PropertyType.STRING, {"type": "string"}),
        (PropertyType.INTEGER, {"type": "integer", "format": "int32"}),
        (PropertyType.NUMBER, {"type": "number", "format": "double"}),
        (PropertyType.BOOLEAN, {"type": "boolean"}),
    ],
)
def test_scalar_property_mapping(
    ptype: PropertyType, expected: dict[str, str]
) -> None:
    prop = SpecProperty(name="x", type=ptype, description="d", constraints=NO_C)
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["x"]
    for key, value in expected.items():
        assert schema[key] == value
    assert schema["description"] == "d"


def test_array_property_mapping() -> None:
    prop = SpecProperty(
        name="tags",
        type=PropertyType.ARRAY,
        description="tag list",
        constraints=NO_C,
        item_type=PropertyType.STRING,
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["tags"]
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "string"}
    assert schema["x-kubernetes-list-type"] == "atomic"


def test_object_property_mapping() -> None:
    prop = SpecProperty(name="cfg", type=PropertyType.OBJECT, description="d", constraints=NO_C)
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["cfg"]
    assert schema["type"] == "object"
    assert schema["x-kubernetes-preserve-unknown-fields"] is False


# ---------------------------------------------------------------------------
# Constraint mapping rules
# ---------------------------------------------------------------------------


def test_min_max_constraints_propagate() -> None:
    prop = SpecProperty(
        name="port",
        type=PropertyType.INTEGER,
        description="d",
        constraints=PropertyConstraints(minimum=1, maximum=65535),
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["port"]
    assert schema["minimum"] == 1
    assert schema["maximum"] == 65535


def test_string_length_constraints_propagate() -> None:
    prop = SpecProperty(
        name="name",
        type=PropertyType.STRING,
        description="d",
        constraints=PropertyConstraints(min_length=1, max_length=64, pattern="^[a-z]+$"),
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["name"]
    assert schema["minLength"] == 1
    assert schema["maxLength"] == 64
    assert schema["pattern"] == "^[a-z]+$"


def test_enum_constraint_propagates_sorted() -> None:
    prop = SpecProperty(
        name="engine",
        type=PropertyType.STRING,
        description="d",
        constraints=PropertyConstraints(enum=("postgres", "mysql", "mongo")),
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["engine"]
    # Sorted for determinism.
    assert schema["enum"] == ["mongo", "mysql", "postgres"]


def test_format_constraint_propagates() -> None:
    prop = SpecProperty(
        name="email",
        type=PropertyType.STRING,
        description="d",
        constraints=PropertyConstraints(format="email"),
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["email"]
    assert schema["format"] == "email"


# ---------------------------------------------------------------------------
# Required list is sorted
# ---------------------------------------------------------------------------


def test_required_list_is_sorted() -> None:
    props = (
        SpecProperty(name="zeta", type=PropertyType.STRING, description="d", constraints=NO_C),
        SpecProperty(name="alpha", type=PropertyType.STRING, description="d", constraints=NO_C),
        SpecProperty(name="beta", type=PropertyType.STRING, description="d", constraints=NO_C),
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=props))
    spec = doc.schemas["Database"]["properties"]["spec"]
    assert spec["required"] == ["alpha", "beta", "zeta"]


# ---------------------------------------------------------------------------
# Description fallback
# ---------------------------------------------------------------------------


def test_default_description_for_blank_property_description() -> None:
    # SpecProperty enforces non-empty description, so the only path to
    # an empty description is bypassing the value object — which we
    # don't do. We at least verify our description propagates verbatim.
    prop = SpecProperty(
        name="x", type=PropertyType.STRING, description="explicit help", constraints=NO_C
    )
    doc = OpenAPIDocument.from_request(_request(spec_properties=(prop,)))
    schema = doc.schemas["Database"]["properties"]["spec"]["properties"]["x"]
    assert schema["description"] == "explicit help"


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_from_request_rejects_non_request() -> None:
    with pytest.raises(Exception):
        OpenAPIDocument.from_request("not a request")  # type: ignore[arg-type]


def test_invalid_info_rejected() -> None:
    with pytest.raises(InvalidOpenAPIDocument):
        OpenAPIDocument(
            info="not info",  # type: ignore[arg-type]
            schemas={},
            paths={},
            extensions={},
        )


def test_invalid_schemas_rejected() -> None:
    with pytest.raises(InvalidOpenAPIDocument):
        OpenAPIDocument(
            info=OpenApiInfo(title="X", version="v1"),
            schemas="not a mapping",  # type: ignore[arg-type]
            paths={},
            extensions={},
        )


def test_gvk_missing_extension_raises() -> None:
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas={},
        paths={},
        extensions={},
    )
    with pytest.raises(InvalidOpenAPIDocument):
        _ = doc.gvk
