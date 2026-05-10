"""Unit tests for :class:`KustomizationGenerator`."""

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
from ai_platform_generator.domain.generation.generators import KustomizationGenerator
from ai_platform_generator.domain.generation.generators.kustomization import (
    KUSTOMIZATION_FILENAME,
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
    gen = KustomizationGenerator()
    assert gen.name == "kustomization"
    assert gen.artefact_type is ArtifactType.KUSTOMIZATION


# ----------------------------------------------------------------------
# Output shape
# ----------------------------------------------------------------------
def test_emits_a_single_file_at_bundle_root(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """Bundle root, not under a subdirectory."""
    _req, ir = request_ir
    arts = KustomizationGenerator().generate(ir, tmp_path)
    assert len(arts) == 1
    assert arts[0].path.as_posix() == KUSTOMIZATION_FILENAME
    # Filename matches the constant we re-export.
    assert KUSTOMIZATION_FILENAME == "kustomization.yaml"


def test_artefact_type_tag(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    art = KustomizationGenerator().generate(ir, tmp_path)[0]
    assert art.artefact_type is ArtifactType.KUSTOMIZATION


def test_yaml_parses_cleanly(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    payload = KustomizationGenerator().generate(ir, tmp_path)[0].payload
    doc = yaml.safe_load(payload)
    assert isinstance(doc, dict)


# ----------------------------------------------------------------------
# Content per spec
# ----------------------------------------------------------------------
def test_top_level_fields(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    doc = yaml.safe_load(
        KustomizationGenerator().generate(ir, tmp_path)[0].payload
    )
    assert doc["apiVersion"] == "kustomize.config.k8s.io/v1beta1"
    assert doc["kind"] == "Kustomization"


def test_resources_reference_crd_and_instance_files(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(
        KustomizationGenerator().generate(ir, tmp_path)[0].payload
    )
    kind_lower = req.gvk.kind.value.lower()
    expected = sorted(
        [f"{kind_lower}.crd.yaml", f"{kind_lower}.instance.yaml"]
    )
    assert doc["resources"] == expected


def test_resources_are_lex_sorted(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    _req, ir = request_ir
    doc = yaml.safe_load(
        KustomizationGenerator().generate(ir, tmp_path)[0].payload
    )
    resources = doc["resources"]
    assert resources == sorted(resources)


def test_common_labels(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    req, ir = request_ir
    doc = yaml.safe_load(
        KustomizationGenerator().generate(ir, tmp_path)[0].payload
    )
    kind_lower = req.gvk.kind.value.lower()
    labels = doc["commonLabels"]
    assert labels["app.kubernetes.io/managed-by"] == "ai-platform-generator"
    assert labels["app.kubernetes.io/name"] == kind_lower


def test_common_labels_keys_lex_sorted(
    request_ir: tuple[CodegenRequest, OpenAPIDocument], tmp_path: Path
) -> None:
    """The keys are sorted in the *raw text* of the YAML.

    PyYAML's ``safe_load`` preserves insertion order in modern Python,
    so we can re-serialise the parsed dict and check that round-trip
    matches the source byte-for-byte under our emit settings.
    """
    _req, ir = request_ir
    payload = KustomizationGenerator().generate(ir, tmp_path)[0].payload
    text = payload.decode("utf-8")
    # Find the labels block — PyYAML emits keys in dict insertion
    # order, and we built the dict from a sorted list, so the keys
    # should appear in lex-sorted order in the raw YAML.
    label_lines = [
        line.strip()
        for line in text.splitlines()
        if line.startswith("  app.kubernetes.io/")
    ]
    keys = [line.split(":", 1)[0].strip() for line in label_lines]
    assert keys == sorted(keys)


# ----------------------------------------------------------------------
# Determinism / idempotency
# ----------------------------------------------------------------------
def test_idempotent_across_three_runs(
    request_ir: tuple[CodegenRequest, OpenAPIDocument],
) -> None:
    _req, ir = request_ir
    IdempotencyVerifier().verify_byte_stable(
        KustomizationGenerator(), ir, runs=3
    )


# ----------------------------------------------------------------------
# Preconditions
# ----------------------------------------------------------------------
def test_rejects_non_openapi_ir(tmp_path: Path) -> None:
    gen = KustomizationGenerator()
    with pytest.raises(ArtifactGenerationError):
        gen.generate("not-an-ir", tmp_path)  # type: ignore[arg-type]
