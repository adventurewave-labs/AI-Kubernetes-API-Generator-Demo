"""Tests for ``RequestValidator`` domain service."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.services.request_validator import RequestValidator
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


def _request(**overrides: object) -> CodegenRequest:
    base = {
        "gvk": GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        "spec_properties": (
            SpecProperty(
                name="x",
                type=PropertyType.STRING,
                description="d",
                constraints=PropertyConstraints(),
            ),
        ),
        "output_path": OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        "description": "ok",
        "provider_mode": ProviderMode.LIVE,
    }
    base.update(overrides)
    return CodegenRequest(**base)  # type: ignore[arg-type]


def test_valid_request_yields_no_violations() -> None:
    v = RequestValidator()
    assert v.validate_codegen_request(_request()) == []


def test_returns_list_not_raises() -> None:
    v = RequestValidator()
    result = v.validate_codegen_request(_request())
    assert isinstance(result, list)


def test_validator_is_idempotent() -> None:
    v = RequestValidator()
    req = _request()
    a = v.validate_codegen_request(req)
    b = v.validate_codegen_request(req)
    assert a == b


def test_validator_detects_relative_traversal_path() -> None:
    """We can't actually construct a CodegenRequest with `..` because
    ``OutputPath`` already rejects it. The validator's traversal check
    is a defence-in-depth measure that we exercise via a stub.
    """

    class _StubOutputPath:
        relative = Path("../bad")
        root = Path(mkdtemp())
        full = root

    req = _request()
    object.__setattr__(req, "output_path", _StubOutputPath())  # type: ignore[arg-type]
    v = RequestValidator()
    violations = v.validate_codegen_request(req)
    assert any(violation.path == "output_path.relative" for violation in violations)
