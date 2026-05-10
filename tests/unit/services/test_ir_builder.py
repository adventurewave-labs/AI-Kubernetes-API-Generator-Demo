"""Tests for ``IRBuilder`` domain service."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import OpenAPIDocument
from ai_platform_generator.domain.services.ir_builder import IRBuilder
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


def _request() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        spec_properties=(
            SpecProperty(
                name="x",
                type=PropertyType.STRING,
                description="d",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="d",
        provider_mode=ProviderMode.LIVE,
    )


def test_ir_builder_returns_openapi_document() -> None:
    builder = IRBuilder()
    doc = builder.build(_request())
    assert isinstance(doc, OpenAPIDocument)


def test_ir_builder_is_deterministic() -> None:
    builder = IRBuilder()
    req = _request()
    a = builder.build(req).serialise()
    b = builder.build(req).serialise()
    assert a == b


def test_ir_builder_matches_factory() -> None:
    builder = IRBuilder()
    req = _request()
    a = builder.build(req).serialise()
    b = OpenAPIDocument.from_request(req).serialise()
    assert a == b
