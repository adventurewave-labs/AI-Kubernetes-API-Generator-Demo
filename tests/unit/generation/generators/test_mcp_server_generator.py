"""Unit tests for :class:`McpServerGenerator`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import (
    ArtifactType,
    CodegenRequest,
    OpenAPIDocument,
)
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.generators import McpServerGenerator
from ai_platform_generator.domain.generation.generators.mcp_server import (
    MCP_DIRNAME,
    MCP_README_FILENAME,
    MCP_REQUIREMENTS_FILENAME,
    MCP_SERVER_FILENAME,
)
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)


# ----------------------------------------------------------------------
# Per-scenario parametrisation
# ----------------------------------------------------------------------
@pytest.fixture(params=DemoCatalog().scenarios, ids=lambda s: s.name)
def scenario(request: pytest.FixtureRequest) -> Any:
    return request.param


@pytest.fixture
def request_ir(scenario: Any) -> tuple[CodegenRequest, OpenAPIDocument]:
    req = CodegenRequest.from_dict(scenario.request)
    return req, OpenAPIDocument.from_request(req)


# ----------------------------------------------------------------------
# Class metadata
# ----------------------------------------------------------------------
def test_metadata() -> None:
    gen = McpServerGenerator()
    assert gen.name == "mcp_server"
    assert gen.artefact_type is ArtifactType.MCP_SERVER


# ----------------------------------------------------------------------
# Output shape
# ----------------------------------------------------------------------
def test_emits_three_files_under_mcp(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    paths = sorted(art.path.as_posix() for art in arts)
    assert paths == sorted(
        [
            f"{MCP_DIRNAME}/{MCP_SERVER_FILENAME}",
            f"{MCP_DIRNAME}/{MCP_REQUIREMENTS_FILENAME}",
            f"{MCP_DIRNAME}/{MCP_README_FILENAME}",
        ]
    )


def test_artefact_type_tag(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    for art in arts:
        assert art.artefact_type is ArtifactType.MCP_SERVER


# ----------------------------------------------------------------------
# server.py contents
# ----------------------------------------------------------------------
def _payload_for(arts: tuple[Any, ...], filename: str) -> str:
    for art in arts:
        if art.path.name == filename:
            return art.payload.decode("utf-8")
    raise AssertionError(f"no artefact named {filename!r} in {arts!r}")


def test_server_py_imports_fastmcp(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_SERVER_FILENAME)
    assert "from mcp.server.fastmcp import FastMCP" in text


def test_server_py_defines_main(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_SERVER_FILENAME)
    assert "def main()" in text
    assert 'if __name__ == "__main__":' in text
    assert "    main()" in text


def test_server_py_defines_one_tool_per_spec_property(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """Tool count must match the IR's spec-property count exactly."""
    req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_SERVER_FILENAME)
    # Count @mcp.tool() decorators.
    tool_count = text.count("@mcp.tool()")
    assert tool_count == len(req.spec_properties)
    # Every property name appears as a get_<prop> function.
    for prop in req.spec_properties:
        assert f"def get_{prop.name}(name: str)" in text


def test_server_py_module_docstring_references_gvk(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_SERVER_FILENAME)
    # The first docstring line mentions kind and group/version.
    assert req.gvk.kind.value in text
    assert req.gvk.group.value in text
    assert req.gvk.version.value in text


# ----------------------------------------------------------------------
# requirements.txt contents
# ----------------------------------------------------------------------
def test_requirements_pins_mcp_and_pydantic(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_REQUIREMENTS_FILENAME)
    lines = [line for line in text.splitlines() if line.strip()]
    assert "mcp>=0.9" in lines
    assert "pydantic>=2.5" in lines


# ----------------------------------------------------------------------
# README.md contents
# ----------------------------------------------------------------------
def test_readme_references_gvk(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """README mentions group, version, and kind from the source CRD."""
    req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_README_FILENAME)
    assert req.gvk.group.value in text
    assert req.gvk.version.value in text
    assert req.gvk.kind.value in text


def test_readme_marks_scaffold_status(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """README must clearly say it is a scaffold."""
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_README_FILENAME)
    assert "scaffold" in text.lower()


def test_readme_has_run_instructions(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    arts = McpServerGenerator().generate(ir, tmp_path)
    text = _payload_for(arts, MCP_README_FILENAME)
    assert "pip install -r requirements.txt" in text
    assert "python server.py" in text


# ----------------------------------------------------------------------
# Determinism / idempotency
# ----------------------------------------------------------------------
def test_idempotent_across_three_runs(
    request_ir: tuple[CodegenRequest, OpenAPIDocument],
) -> None:
    _req, ir = request_ir
    IdempotencyVerifier().verify_byte_stable(McpServerGenerator(), ir, runs=3)


# ----------------------------------------------------------------------
# Preconditions
# ----------------------------------------------------------------------
def test_rejects_non_openapi_ir(tmp_path: Path) -> None:
    gen = McpServerGenerator()
    with pytest.raises(ArtifactGenerationError):
        gen.generate("not-an-ir", tmp_path)  # type: ignore[arg-type]
