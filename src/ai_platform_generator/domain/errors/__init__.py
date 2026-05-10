"""Domain error taxonomy.

Public re-exports for the typed exception hierarchy described in
ADR-0016. Names are sorted alphabetically; ``__all__`` is enumerated so
``from ... import *`` picks up exactly the public surface.
"""
from __future__ import annotations

from .artifact import (
    ArtifactGenerationError,
    ChecksumMismatch,
    PostProcessingFailed,
    TemplateRenderingError,
)
from .base import PlatformGeneratorError
from .cluster import (
    ClusterCreationTimedOut,
    ClusterProvisioningError,
    CrdNotEstablished,
    DeploymentVerificationFailed,
    KubectlInvocationFailed,
    ResourceVerificationFailed,
)
from .configuration import (
    ConfigurationError,
    InvalidConfigFile,
    MissingApiKey,
    PrerequisiteMissing,
)
from .domain_validation import (
    DomainValidationError,
    EmptySpec,
    InvalidChecksum,
    InvalidGroup,
    InvalidIntent,
    InvalidKind,
    InvalidOutputPath,
    InvalidPropertyConstraints,
    InvalidRunId,
    InvalidSpecProperty,
    InvalidVersion,
    UnsupportedSchema,
)
from .field_violation import FieldViolation
from .intent import (
    AmbiguousIntent,
    IntentInterpretationError,
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
)
from .persistence import (
    ArtifactWriteFailed,
    PersistenceError,
    ProvenanceCorrupted,
)

__all__ = [
    "AmbiguousIntent",
    "ArtifactGenerationError",
    "ArtifactWriteFailed",
    "ChecksumMismatch",
    "ClusterCreationTimedOut",
    "ClusterProvisioningError",
    "ConfigurationError",
    "CrdNotEstablished",
    "DeploymentVerificationFailed",
    "DomainValidationError",
    "EmptySpec",
    "FieldViolation",
    "IntentInterpretationError",
    "InvalidChecksum",
    "InvalidConfigFile",
    "InvalidGroup",
    "InvalidIntent",
    "InvalidKind",
    "InvalidOutputPath",
    "InvalidPropertyConstraints",
    "InvalidRunId",
    "InvalidSpecProperty",
    "InvalidVersion",
    "KubectlInvocationFailed",
    "LlmAuthenticationFailed",
    "LlmRateLimited",
    "LlmResponseUnparseable",
    "LlmUnavailable",
    "MissingApiKey",
    "PersistenceError",
    "PlatformGeneratorError",
    "PostProcessingFailed",
    "PrerequisiteMissing",
    "ProvenanceCorrupted",
    "ResourceVerificationFailed",
    "TemplateRenderingError",
    "UnsupportedSchema",
]
