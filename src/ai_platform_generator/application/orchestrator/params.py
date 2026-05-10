"""``GenerateParams`` DTO.

Exposed at the public surface of the application layer per
``docs/ddd/06-application-services.md`` §5. Used by every CLI command
that drives a generation run.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtifactType(str, Enum):
    """Wire-stable enum of the artefact types a run can produce.

    Matches the values listed in
    ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §3. Defined
    here as a fallback while Agent G's ``domain.aggregates.ArtifactType``
    is in flight; the values are intentionally identical so a future
    rename is mechanical.
    """

    OPENAPI = "OPENAPI"
    CRD = "CRD"
    INSTANCE = "INSTANCE"
    GO_CONTROLLER = "GO_CONTROLLER"
    MCP_SERVER = "MCP_SERVER"
    KUSTOMIZATION = "KUSTOMIZATION"


_DEFAULT_GENERATORS: list[ArtifactType] = [
    ArtifactType.OPENAPI,
    ArtifactType.CRD,
    ArtifactType.INSTANCE,
]


class GenerateParams(BaseModel):
    """The full set of inputs a Generation Run accepts.

    See ``docs/ddd/06-application-services.md`` §5.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_text: str = Field(min_length=1)
    output_dir: Path | None = None
    deploy_to_cluster: bool = True
    cluster_name: str = "ai-platform-demo"
    allow_demo_mode: bool = True
    requested_generators: list[ArtifactType] = Field(
        default_factory=lambda: list(_DEFAULT_GENERATORS),
    )
    capture_prompts: bool = False
    log_format: Literal["tty", "json", "quiet"] = "tty"
