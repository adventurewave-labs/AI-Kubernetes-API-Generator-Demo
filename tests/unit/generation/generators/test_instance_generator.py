"""Unit tests for :class:`InstanceYamlGenerator`."""

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
from ai_platform_generator.domain.generation.generators import InstanceYamlGenerator
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)
from ai_platform_generator.domain.values import PropertyType


@pytest.fixture(params=DemoCatalog().scenarios, ids=lambda s: s.name)
def scenario(request: pytest.FixtureRequest) -> Any:
    return request.param


@pytest.fixture
def request_ir(scenario: Any) -> tuple[CodegenRequest, OpenAPIDocument]:
    req = CodegenRequest.from_dict(scenario.request)
    return req, OpenAPIDocument.from_request(req)


def test_metadata() -> None:
    gen = InstanceYamlGenerator()
    assert gen.name == "instance"
    assert gen.artefact_type is ArtifactType.INSTANCE


def test_filename_is_kindlower_instance_yaml(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    art = InstanceYamlGenerator().generate(ir, tmp_path)[0]
    expected = f"{req.gvk.kind.value.lower()}.instance.yaml"
    assert art.path.as_posix() == expected


def test_yaml_parses_cleanly(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    payload = InstanceYamlGenerator().generate(ir, tmp_path)[0].payload
    doc = yaml.safe_load(payload)
    assert isinstance(doc, dict)


def test_top_level_fields(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(InstanceYamlGenerator().generate(ir, tmp_path)[0].payload)
    assert doc["apiVersion"] == req.gvk.api_version
    assert doc["kind"] == req.gvk.kind.value


def test_metadata_block(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(InstanceYamlGenerator().generate(ir, tmp_path)[0].payload)
    metadata = doc["metadata"]
    assert metadata["name"] == f"my-{req.gvk.kind.value.lower()}-instance"
    assert metadata["namespace"] == "default"


def test_every_spec_property_is_present_with_correct_shape(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """Each declared property should have a placeholder of the right Python type."""
    req, ir = request_ir
    doc = yaml.safe_load(InstanceYamlGenerator().generate(ir, tmp_path)[0].payload)
    spec = doc["spec"]
    assert isinstance(spec, dict)
    assert set(spec.keys()) == {p.name for p in req.spec_properties}

    for prop in req.spec_properties:
        value = spec[prop.name]
        if prop.type is PropertyType.STRING:
            assert isinstance(value, str)
            if prop.constraints.enum:
                # Enum-constrained strings must be one of the enum values.
                assert value in prop.constraints.enum
        elif prop.type is PropertyType.INTEGER:
            assert isinstance(value, int) and not isinstance(value, bool)
            if prop.constraints.minimum is not None:
                assert value >= prop.constraints.minimum
        elif prop.type is PropertyType.NUMBER:
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
        elif prop.type is PropertyType.BOOLEAN:
            assert isinstance(value, bool)
        elif prop.type is PropertyType.ARRAY:
            assert isinstance(value, list)
            assert len(value) >= 1
        elif prop.type is PropertyType.OBJECT:
            assert isinstance(value, dict)


def test_string_enum_picks_first_value(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """For string properties with an enum, the placeholder is one of them.

    The IR sorts ``enum`` lex-ascending, so we take ``enum[0]`` from the
    schema (which is the lex-smallest value).
    """
    req, ir = request_ir
    doc = yaml.safe_load(InstanceYamlGenerator().generate(ir, tmp_path)[0].payload)
    for prop in req.spec_properties:
        if prop.type is PropertyType.STRING and prop.constraints.enum:
            spec_value = doc["spec"][prop.name]
            assert spec_value == sorted(prop.constraints.enum)[0]


def test_byte_stable_across_runs(
    request_ir: tuple[CodegenRequest, OpenAPIDocument],
) -> None:
    _req, ir = request_ir
    IdempotencyVerifier().verify_byte_stable(InstanceYamlGenerator(), ir, runs=3)


def test_rejects_non_openapi_input(tmp_path: Path) -> None:
    with pytest.raises(ArtifactGenerationError, match="OpenAPIDocument"):
        InstanceYamlGenerator().generate("nope", tmp_path)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# default_generators factory
# ----------------------------------------------------------------------
def test_default_generators_factory_includes_three_core_generators() -> None:
    """The factory must surface the three core generators (Agent L's scope).

    Sibling agents may register additional generators (Go controller,
    Kustomization, MCP server); we only assert that the three Agent-L
    generators are present and appear in the expected on-disk order
    relative to one another. This keeps the test stable across
    parallel-agent rebases.
    """
    from ai_platform_generator.domain.generation.generators import default_generators

    gens = default_generators()
    names = [g.name for g in gens]
    for required in ("openapi", "crd", "instance"):
        assert required in names, (
            f"default_generators() missing {required!r}; got {names!r}"
        )
    # Relative order: openapi < crd < instance.
    assert names.index("openapi") < names.index("crd") < names.index(
        "instance"
    ), f"unexpected generator ordering: {names!r}"
