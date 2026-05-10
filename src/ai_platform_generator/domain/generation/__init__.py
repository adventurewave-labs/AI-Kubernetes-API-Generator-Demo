"""Artifact-Generation bounded-context internals.

Public re-exports for the building blocks that live inside the
``Artifact Generation`` bounded context but are *not* aggregates (those
are owned by ``ai_platform_generator.domain.aggregates``).

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` for the
context boundary.
"""

from __future__ import annotations

from ai_platform_generator.domain.generation.artifact_generator import (
    DEFAULT_FILE_MODE,
    ArtifactGenerator,
    get_registered_generators,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.idempotency_verifier import (
    IdempotencyVerifier,
)
from ai_platform_generator.domain.generation.provenance_factory import (
    ProvenanceManifestFactory,
)
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile
from ai_platform_generator.domain.generation.renderer import Renderer

__all__ = [
    "DEFAULT_FILE_MODE",
    "ArtifactGenerator",
    "GenerationPlan",
    "IdempotencyVerifier",
    "ProvenanceManifestFactory",
    "Renderer",
    "_RenderedFile",
    "get_registered_generators",
    "register_generator",
]
