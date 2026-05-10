"""Unit tests for :class:`OpenApiGenerator`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import (
    ArtifactType,
    CodegenRequest,
    OpenAPIDocument,
)
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.generators import OpenApiGenerator
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)


@pytest.fixture(params=DemoCatalog().scenarios, ids=lambda s: s.name)
def scenario_ir(request: pytest.FixtureRequest) -> OpenAPIDocument:
    """Yield an IR for each canonical demo scenario."""
    return OpenAPIDocument.from_request(CodegenRequest.from_dict(request.param.request))


def test_metadata(scenario_ir: OpenAPIDocument) -> None:
    gen = OpenApiGenerator()
    assert gen.name == "openapi"
    assert gen.artefact_type is ArtifactType.OPENAPI


def test_emits_single_openapi_json(
    scenario_ir: OpenAPIDocument, tmp_path: Path
) -> None:
    gen = OpenApiGenerator()
    artefacts = gen.generate(scenario_ir, tmp_path)
    assert len(artefacts) == 1
    art = artefacts[0]
    assert art.path.as_posix() == "openapi.json"
    assert art.artefact_type is ArtifactType.OPENAPI


def test_payload_is_serialised_ir(
    scenario_ir: OpenAPIDocument, tmp_path: Path
) -> None:
    gen = OpenApiGenerator()
    art = gen.generate(scenario_ir, tmp_path)[0]
    assert art.payload == scenario_ir.serialise(indent=2)


def test_round_trip_loads_back_into_equivalent_dict(
    scenario_ir: OpenAPIDocument, tmp_path: Path
) -> None:
    """The serialised bytes should JSON-decode to the IR's canonical dict."""
    gen = OpenApiGenerator()
    art = gen.generate(scenario_ir, tmp_path)[0]
    decoded = json.loads(art.payload.decode("utf-8"))
    assert decoded == scenario_ir.to_dict()


def test_byte_stable_across_runs(scenario_ir: OpenAPIDocument) -> None:
    """``IdempotencyVerifier`` should accept three back-to-back runs."""
    IdempotencyVerifier().verify_byte_stable(OpenApiGenerator(), scenario_ir, runs=3)


# ----------------------------------------------------------------------
# Preconditions
# ----------------------------------------------------------------------
def test_rejects_non_openapi_input(tmp_path: Path) -> None:
    gen = OpenApiGenerator()
    with pytest.raises(ArtifactGenerationError, match="OpenAPIDocument"):
        gen.generate("not-an-ir", tmp_path)  # type: ignore[arg-type]
