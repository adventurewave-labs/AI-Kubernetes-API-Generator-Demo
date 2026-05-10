"""Tests for ``StructuralSchemaValidator`` domain service."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp
from types import MappingProxyType

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import (
    OpenAPIDocument,
    OpenApiInfo,
)
from ai_platform_generator.domain.services.structural_schema_validator import (
    StructuralSchemaValidator,
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


def _ok_request() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        spec_properties=(
            SpecProperty(
                name="replicas",
                type=PropertyType.INTEGER,
                description="d",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="d",
        provider_mode=ProviderMode.LIVE,
    )


def test_valid_ir_has_no_violations() -> None:
    doc = OpenAPIDocument.from_request(_ok_request())
    v = StructuralSchemaValidator()
    assert v.validate(doc) == []


def test_missing_type_at_property_flagged() -> None:
    bad_schema = {
        "type": "object",
        "description": "X",
        "properties": {
            "spec": {
                # 'type' missing here.
                "description": "spec",
                "properties": {},
            }
        },
    }
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas=MappingProxyType({"X": bad_schema}),
        paths=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    v = StructuralSchemaValidator()
    violations = v.validate(doc)
    paths = {viol.path for viol in violations}
    assert any(p.endswith(".spec.type") for p in paths)


def test_oneof_anyof_not_flagged() -> None:
    bad_schema = {
        "type": "object",
        "description": "X",
        "properties": {
            "x": {
                "type": "object",
                "description": "d",
                "oneOf": [{"type": "string"}, {"type": "integer"}],
            }
        },
    }
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas=MappingProxyType({"X": bad_schema}),
        paths=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    v = StructuralSchemaValidator()
    violations = v.validate(doc)
    assert any(viol.path.endswith(".oneOf") for viol in violations)


def test_additional_properties_true_flagged() -> None:
    bad_schema = {
        "type": "object",
        "description": "X",
        "properties": {
            "x": {
                "type": "object",
                "description": "d",
                "additionalProperties": True,
            }
        },
    }
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas=MappingProxyType({"X": bad_schema}),
        paths=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    v = StructuralSchemaValidator()
    violations = v.validate(doc)
    assert any(viol.path.endswith(".additionalProperties") for viol in violations)


def test_additional_properties_true_with_preserve_unknown_ok() -> None:
    schema = {
        "type": "object",
        "description": "X",
        "properties": {
            "x": {
                "type": "object",
                "description": "d",
                "additionalProperties": True,
                "x-kubernetes-preserve-unknown-fields": True,
            }
        },
    }
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas=MappingProxyType({"X": schema}),
        paths=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    v = StructuralSchemaValidator()
    violations = v.validate(doc)
    assert all(not viol.path.endswith(".additionalProperties") for viol in violations)


def test_missing_description_on_named_property_flagged() -> None:
    bad_schema = {
        "type": "object",
        "description": "X",
        "properties": {
            "x": {
                "type": "string",
                # description missing.
            }
        },
    }
    doc = OpenAPIDocument(
        info=OpenApiInfo(title="X", version="v1"),
        schemas=MappingProxyType({"X": bad_schema}),
        paths=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    v = StructuralSchemaValidator()
    violations = v.validate(doc)
    assert any(viol.path.endswith(".description") for viol in violations)
