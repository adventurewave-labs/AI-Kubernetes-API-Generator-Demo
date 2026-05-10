"""Tests for ``RequestEnhancer`` domain service."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.services.request_enhancer import RequestEnhancer
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


def _request(
    output_path: OutputPath | None = None,
    description: str = "ok",
) -> CodegenRequest:
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
        output_path=output_path or OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description=description,
        provider_mode=ProviderMode.LIVE,
    )


def test_enhance_does_nothing_when_already_filled() -> None:
    root = Path(mkdtemp())
    enh = RequestEnhancer(default_root=root)
    req = _request()
    out = enh.enhance(req)
    assert out == req


def test_enhance_replaces_default_relative_path() -> None:
    root = Path(mkdtemp())
    enh = RequestEnhancer(default_root=root)
    sentinel = OutputPath(root=root, relative=Path("__default__"))
    req = _request(output_path=sentinel)
    out = enh.enhance(req)
    assert out.output_path.relative == Path("generated_specs") / "database"
    assert out.output_path.root == root


def test_enhance_replaces_default_description() -> None:
    enh = RequestEnhancer()
    req = _request(description="__default__")
    out = enh.enhance(req)
    assert "Database" in out.description
    assert out.description != "__default__"


def test_enhance_preserves_other_fields() -> None:
    root = Path(mkdtemp())
    enh = RequestEnhancer(default_root=root)
    req = _request(description="__default__")
    out = enh.enhance(req)
    assert out.gvk == req.gvk
    assert out.spec_properties == req.spec_properties
    assert out.provider_mode is req.provider_mode


def test_enhance_is_idempotent() -> None:
    root = Path(mkdtemp())
    enh = RequestEnhancer(default_root=root)
    req = _request(
        output_path=OutputPath(root=root, relative=Path("__default__")),
        description="__default__",
    )
    a = enh.enhance(req)
    b = enh.enhance(a)
    assert a == b
