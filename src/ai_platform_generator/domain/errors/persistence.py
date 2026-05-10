"""Persistence errors — writing artefacts and the provenance manifest."""
from __future__ import annotations

from .base import PlatformGeneratorError


class PersistenceError(PlatformGeneratorError):
    """Base class for filesystem / store interactions that fail."""

    code = "E_PERSISTENCE_GENERIC"


class ArtifactWriteFailed(PersistenceError):
    """An artefact could not be written to its target path."""

    code = "E_PERSISTENCE_ARTIFACT_WRITE_FAILED"


class ProvenanceCorrupted(PersistenceError):
    """The provenance manifest is missing entries or has bad checksums."""

    code = "E_PERSISTENCE_PROVENANCE_CORRUPTED"
