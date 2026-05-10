"""Artifact-generation errors.

Raised by generators while planning, rendering, post-processing or sealing
a bundle.
"""
from __future__ import annotations

from .base import PlatformGeneratorError


class ArtifactGenerationError(PlatformGeneratorError):
    """Base class for generation-time problems."""

    code = "E_ARTIFACT_GENERIC"


class TemplateRenderingError(ArtifactGenerationError):
    """A Jinja (or other) template raised while rendering an artefact."""

    code = "E_ARTIFACT_TEMPLATE_RENDERING"


class PostProcessingFailed(ArtifactGenerationError):
    """Post-processing (gofmt / yamlfmt / similar) failed for an artefact."""

    code = "E_ARTIFACT_POST_PROCESSING_FAILED"


class ChecksumMismatch(ArtifactGenerationError):
    """An artefact's recorded checksum does not match its on-disk content."""

    code = "E_ARTIFACT_CHECKSUM_MISMATCH"
