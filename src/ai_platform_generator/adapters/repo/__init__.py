"""Repository / persistence adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.repo.filesystem import (
    FilesystemArtifactRepository,
)
from ai_platform_generator.adapters.repo.in_memory import InMemoryArtifactRepository

__version__ = "0.1.0"

__all__ = [
    "FilesystemArtifactRepository",
    "InMemoryArtifactRepository",
    "__version__",
]
