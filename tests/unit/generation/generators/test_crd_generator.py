"""Unit tests for :class:`CrdYamlGenerator`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import (
    ArtifactType,
    CodegenRequest,
    OpenAPIDocument,
)
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.generators import CrdYamlGenerator
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)


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
    gen = CrdYamlGenerator()
    assert gen.name == "crd"
    assert gen.artefact_type is ArtifactType.CRD


# ----------------------------------------------------------------------
# Mapping per ADR-0005 / bounded-context-03 §6.2.1
# ----------------------------------------------------------------------
def test_filename_is_kindlower_crd_yaml(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    art = CrdYamlGenerator().generate(ir, tmp_path)[0]
    expected = f"{req.gvk.kind.value.lower()}.crd.yaml"
    assert art.path.as_posix() == expected


def test_yaml_parses_cleanly(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    payload = CrdYamlGenerator().generate(ir, tmp_path)[0].payload
    doc = yaml.safe_load(payload)
    assert isinstance(doc, dict)


def test_top_level_fields(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    assert doc["apiVersion"] == "apiextensions.k8s.io/v1"
    assert doc["kind"] == "CustomResourceDefinition"
    assert doc["metadata"]["name"] == req.gvk.crd_name


def test_spec_group_and_scope(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    assert doc["spec"]["group"] == req.gvk.group.value
    assert doc["spec"]["scope"] == "Namespaced"


def test_spec_names_block(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    names = doc["spec"]["names"]
    assert names["kind"] == req.gvk.kind.value
    assert names["listKind"] == f"{req.gvk.kind.value}List"
    assert names["plural"] == req.gvk.kind.plural
    assert names["singular"] == req.gvk.kind.singular
    assert names["shortNames"] == []


def test_versions_first_entry_shape(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    versions = doc["spec"]["versions"]
    assert isinstance(versions, list) and len(versions) == 1
    v0 = versions[0]
    assert v0["name"] == req.gvk.version.value
    assert v0["served"] is True
    assert v0["storage"] is True
    assert v0["subresources"] == {"status": {}}
    schema = v0["schema"]["openAPIV3Schema"]
    assert schema["type"] == "object"


def test_schema_strips_apiversion_kind_metadata(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """Kubernetes injects these top-level fields — they must not appear."""
    _req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    schema = doc["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    properties = schema.get("properties", {})
    assert "apiVersion" not in properties
    assert "kind" not in properties
    assert "metadata" not in properties
    # spec and status survive.
    assert "spec" in properties
    assert "status" in properties


def test_required_array_is_sorted(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    schema = doc["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    if "required" in schema:
        assert schema["required"] == sorted(schema["required"])


def test_spec_properties_match_request(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """Every declared spec property surfaces in the schema."""
    req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    schema = doc["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    spec_props = schema["properties"]["spec"]["properties"]
    expected_names = {p.name for p in req.spec_properties}
    assert set(spec_props.keys()) == expected_names


def test_status_subresource_present(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    doc = yaml.safe_load(CrdYamlGenerator().generate(ir, tmp_path)[0].payload)
    assert doc["spec"]["versions"][0]["subresources"]["status"] == {}


# ----------------------------------------------------------------------
# Determinism
# ----------------------------------------------------------------------
def test_byte_stable_across_runs(
    request_ir: tuple[CodegenRequest, OpenAPIDocument],
) -> None:
    _req, ir = request_ir
    IdempotencyVerifier().verify_byte_stable(CrdYamlGenerator(), ir, runs=3)


def test_rerender_byte_identical(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    a1 = CrdYamlGenerator().generate(ir, tmp_path)[0].payload
    a2 = CrdYamlGenerator().generate(ir, tmp_path)[0].payload
    assert a1 == a2


# ----------------------------------------------------------------------
# Preconditions
# ----------------------------------------------------------------------
def test_rejects_non_openapi_input(tmp_path: Path) -> None:
    with pytest.raises(ArtifactGenerationError, match="OpenAPIDocument"):
        CrdYamlGenerator().generate("nope", tmp_path)  # type: ignore[arg-type]
