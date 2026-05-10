"""Domain aggregates.

Re-exports the public aggregate types so callers can write
``from ai_platform_generator.domain.aggregates import CodegenRequest``
rather than reaching into individual modules.
"""

from __future__ import annotations

from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactBundle,
    ArtifactRef,
    ArtifactType,
    ProvenanceManifest,
    RenderedArtifact,
)
from ai_platform_generator.domain.aggregates.cluster import (
    Cluster,
    ClusterConfig,
    InvalidCluster,
)
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.generation_run import (
    Deployment,
    GenerationRun,
    RunState,
)
from ai_platform_generator.domain.aggregates.openapi_document import (
    JsonSchema,
    OpenAPIDocument,
    OpenApiInfo,
)

__version__ = "0.1.0"

__all__ = [
    "ArtifactBundle",
    "ArtifactRef",
    "ArtifactType",
    "Cluster",
    "ClusterConfig",
    "CodegenRequest",
    "Deployment",
    "GenerationRun",
    "InvalidCluster",
    "JsonSchema",
    "OpenAPIDocument",
    "OpenApiInfo",
    "ProvenanceManifest",
    "RenderedArtifact",
    "RunState",
    "__version__",
]
