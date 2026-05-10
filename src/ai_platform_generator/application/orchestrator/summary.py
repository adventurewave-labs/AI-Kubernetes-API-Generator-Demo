"""``GenerationSummary`` DTO.

Returned by ``GenerationOrchestrator.run`` and serialised by CLI
adapters. See ``docs/ddd/06-application-services.md`` §5.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


class GenerationSummary(BaseModel):
    """A small, JSON-serialisable summary of a single Generation Run."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    run_id: Any = Field(description="The :class:`RunId` of this run.")
    state: str = Field(description="One of pending/.../succeeded/failed.")
    gvk: Any | None = None
    bundle_dir: Path | None = None
    artefact_paths: list[Path] = Field(default_factory=list)
    cluster_name: str | None = None
    deployment_status: str | None = None
    duration_ms: int = 0
    provider_mode: Any | None = None
