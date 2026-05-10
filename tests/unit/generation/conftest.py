"""Shared fixtures for the Artifact-Generation tests.

Provides minimal *valid* domain instances (``CodegenRequest``,
``OpenAPIDocument``) so individual test modules don't have to repeat
the boilerplate of building one. Most generation tests don't care
about the *content* of the IR — they exercise the lifecycle, the
planner's collision detection, the renderer, etc. — they just need a
correctly-typed instance to pass through.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_platform_generator.domain.aggregates import CodegenRequest, OpenAPIDocument
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


@pytest.fixture
def sample_request(tmp_path: Path) -> CodegenRequest:
    """Return a minimal-but-valid :class:`CodegenRequest`."""
    return CodegenRequest(
        gvk=GVK(
            group=Group("example.com"),
            version=Version("v1"),
            kind=Kind("Widget"),
        ),
        spec_properties=(
            SpecProperty(
                name="size",
                type=PropertyType.INTEGER,
                description="Number of widgets.",
                constraints=PropertyConstraints(),
            ),
        ),
        output_path=OutputPath(root=tmp_path, relative=Path(".")),
        description="A widget for testing.",
        provider_mode=ProviderMode.DEMO,
    )


@pytest.fixture
def sample_ir(sample_request: CodegenRequest) -> OpenAPIDocument:
    """Return a minimal-but-valid :class:`OpenAPIDocument`."""
    return OpenAPIDocument.from_request(sample_request)
