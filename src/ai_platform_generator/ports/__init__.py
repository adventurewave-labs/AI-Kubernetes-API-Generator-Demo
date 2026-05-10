"""Ports: protocols defining boundaries between application and adapters.

Each port is a :class:`typing.Protocol`. See
``docs/ddd/07-anti-corruption-layers.md`` for the full contract per port
and the rationale behind each boundary.
"""

from __future__ import annotations

from ai_platform_generator.ports.artifact_repository import ArtifactRepository
from ai_platform_generator.ports.clock import Clock
from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterEvent,
    ClusterRuntime,
    ClusterStatus,
    MissingTool,
    ResourceDescription,
    ResourceState,
)
from ai_platform_generator.ports.llm_provider import LlmProvider
from ai_platform_generator.ports.run_repository import RunRepository
from ai_platform_generator.ports.secret_provider import SecretProvider
from ai_platform_generator.ports.telemetry_sink import TelemetrySink

__version__ = "0.1.0"

__all__ = [
    # ClusterRuntime support value objects
    "ApplyResult",
    # Protocols
    "ArtifactRepository",
    "Clock",
    "ClusterEvent",
    "ClusterRuntime",
    "ClusterStatus",
    "LlmProvider",
    "MissingTool",
    "ResourceDescription",
    "ResourceState",
    "RunRepository",
    "SecretProvider",
    "TelemetrySink",
    "__version__",
]
