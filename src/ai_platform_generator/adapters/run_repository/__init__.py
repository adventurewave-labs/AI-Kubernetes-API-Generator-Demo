"""Adapters for the :class:`RunRepository` port."""

from __future__ import annotations

from ai_platform_generator.adapters.run_repository.in_memory import (
    InMemoryRunRepository,
)

__version__ = "0.1.0"

__all__ = ["InMemoryRunRepository", "__version__"]
