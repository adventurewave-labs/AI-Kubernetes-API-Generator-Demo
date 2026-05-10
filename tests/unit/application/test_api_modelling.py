"""Unit tests for :class:`ApiModellingService`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_platform_generator.application.services.api_modelling import (
    ApiModellingService,
)
from ai_platform_generator.domain.aggregates.codegen_request import (
    CodegenRequest,
)
from ai_platform_generator.domain.errors import (
    FieldViolation,
    UnsupportedSchema,
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


def _request() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(
            group=Group("platform.example.com"),
            version=Version("v1alpha1"),
            kind=Kind("Foo"),
        ),
        spec_properties=(
            SpecProperty(
                name="bar",
                type=PropertyType.STRING,
                description="something",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=Path.cwd().resolve(), relative=Path("foo")),
        description="A foo.",
        provider_mode=ProviderMode.LIVE,
    )


def test_build_emits_ir_constructed_event(sink) -> None:
    svc = ApiModellingService(events=sink)

    ir = svc.build(_request())

    assert ir.gvk.kind.value == "Foo"
    sink.assert_events_in_order("IRConstructed")
    payload = sink.events_with_name("IRConstructed")[0].payload
    assert payload["gvk"]["kind"] == "Foo"
    assert payload["schema_count"] == 1


def test_build_uses_injected_ir_builder_when_present(sink) -> None:
    class _Builder:
        def __init__(self) -> None:
            self.calls = 0

        def build(self, request: Any) -> Any:
            self.calls += 1
            from ai_platform_generator.domain.aggregates.openapi_document import (
                OpenAPIDocument,
            )

            return OpenAPIDocument.from_request(request)

    builder = _Builder()
    svc = ApiModellingService(events=sink, ir_builder=builder)
    svc.build(_request())
    assert builder.calls == 1


def test_build_raises_unsupported_schema_on_validator_violations(sink) -> None:
    class _RejectingValidator:
        def validate(self, _ir: Any) -> list[FieldViolation]:
            return [
                FieldViolation(
                    path="schemas.Foo",
                    expected="structural",
                    actual="oneOf",
                    message="oneOf is not supported",
                )
            ]

    svc = ApiModellingService(events=sink, validator=_RejectingValidator())

    with pytest.raises(UnsupportedSchema) as excinfo:
        svc.build(_request())

    assert excinfo.value.field_violations
    assert sink.events_with_name("IRRejected")
