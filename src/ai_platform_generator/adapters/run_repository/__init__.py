"""Adapters for the :class:`RunRepository` port."""

from __future__ import annotations

from ai_platform_generator.adapters.run_repository.in_memory import (
    InMemoryRunRepository,
)
from ai_platform_generator.adapters.run_repository.jsonl import JsonlRunRepository

__version__ = "0.1.0"

__all__ = ["InMemoryRunRepository", "JsonlRunRepository", "__version__"]
