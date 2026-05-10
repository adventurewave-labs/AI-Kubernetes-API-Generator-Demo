"""Domain events: envelope, catalogue, and in-process bus.

Public re-exports. The module realises the catalogue from
``docs/ddd/05-domain-events.md`` with one Python class per event so
producers can spell their intent precisely (``IntentSubmitted.make(...)``)
while subscribers continue to switch on the wire-stable
:pyattr:`DomainEvent.name` string.
"""
from __future__ import annotations

from .bus import EventBus, Subscriber
from .catalog import (
    ALL_EVENT_TYPES,
    ArtifactBundleSealed,
    ArtifactGenerated,
    ArtifactGenerationFailed,
    ArtifactPostProcessed,
    ArtifactRendered,
    ClusterCreationFailed,
    ClusterCreationStarted,
    ClusterCreationSucceeded,
    CodegenRequestParsed,
    CodegenRequestRejected,
    CommandFailed,
    CommandStarted,
    CommandSucceeded,
    CompensationApplied,
    CrdApplied,
    DemoModeEngaged,
    DeploymentVerificationFailed,
    DeploymentVerified,
    GenerationPlanned,
    InstanceApplied,
    IntentSubmitted,
    IRConstructed,
    IRRejected,
    LlmInvocationFailed,
    LlmInvocationStarted,
    LlmInvocationSucceeded,
    PrerequisiteCheckFailed,
    PrerequisiteCheckSucceeded,
    RenderModeChosen,
    RunFailed,
    RunStarted,
    RunSucceeded,
    StageFailed,
    StageStarted,
    StageSucceeded,
)
from .envelope import VALID_CONTEXTS, DomainEvent

__version__ = "0.1.0"

__all__ = [
    # core
    "ALL_EVENT_TYPES",
    "VALID_CONTEXTS",
    # catalogue (sorted alphabetically)
    "ArtifactBundleSealed",
    "ArtifactGenerated",
    "ArtifactGenerationFailed",
    "ArtifactPostProcessed",
    "ArtifactRendered",
    "ClusterCreationFailed",
    "ClusterCreationStarted",
    "ClusterCreationSucceeded",
    "CodegenRequestParsed",
    "CodegenRequestRejected",
    "CommandFailed",
    "CommandStarted",
    "CommandSucceeded",
    "CompensationApplied",
    "CrdApplied",
    "DemoModeEngaged",
    "DeploymentVerificationFailed",
    "DeploymentVerified",
    "DomainEvent",
    "EventBus",
    "GenerationPlanned",
    "IRConstructed",
    "IRRejected",
    "InstanceApplied",
    "IntentSubmitted",
    "LlmInvocationFailed",
    "LlmInvocationStarted",
    "LlmInvocationSucceeded",
    "PrerequisiteCheckFailed",
    "PrerequisiteCheckSucceeded",
    "RenderModeChosen",
    "RunFailed",
    "RunStarted",
    "RunSucceeded",
    "StageFailed",
    "StageStarted",
    "StageSucceeded",
    "Subscriber",
    "__version__",
]
