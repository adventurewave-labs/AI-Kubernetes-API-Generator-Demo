"""Domain services.

Stateless logic that doesn't naturally belong to any single aggregate.
See ``docs/ddd/04-tactical-design.md`` section 5 and the per-context
descriptions under ``docs/ddd/bounded-contexts/``.
"""

from __future__ import annotations

from ai_platform_generator.domain.services.artifact_planner import (
    ArtifactPlanner,
    PathCollision,
)
from ai_platform_generator.domain.services.checksum_service import ChecksumService
from ai_platform_generator.domain.services.ir_builder import IRBuilder
from ai_platform_generator.domain.services.request_enhancer import RequestEnhancer
from ai_platform_generator.domain.services.request_validator import RequestValidator
from ai_platform_generator.domain.services.structural_schema_validator import (
    StructuralSchemaValidator,
)

__version__ = "0.1.0"

__all__ = [
    "ArtifactPlanner",
    "ChecksumService",
    "IRBuilder",
    "PathCollision",
    "RequestEnhancer",
    "RequestValidator",
    "StructuralSchemaValidator",
    "__version__",
]
