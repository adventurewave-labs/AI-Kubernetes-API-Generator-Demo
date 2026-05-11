"""Concrete domain-event subclasses.

This module realises the catalogue from ``docs/ddd/05-domain-events.md`` §3:
35 past-tense, immutable, versioned events grouped by producing bounded
context.

Each subclass:

* sets a class-level :pyattr:`NAME` (the stable wire name) and
  :pyattr:`SCHEMA_VERSION` (default ``1``);
* sets a class-level :pyattr:`CONTEXT` matching one of
  :data:`ai_platform_generator.domain.events.envelope.VALID_CONTEXTS`;
* provides :pymeth:`make` — a class method that produces a fully populated
  :class:`DomainEvent` envelope using ``uuid.uuid4()`` and
  ``datetime.now(timezone.utc)``.

Subclasses do *not* introduce new instance state; ``DomainEvent.make`` is a
factory that returns a plain envelope. Callers that need a typed payload
should validate it before calling ``make`` (see ADR-0016).
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID, uuid4

from .envelope import DomainEvent

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.values import RunId
else:
    RunId = Any  # type: ignore[assignment,misc]


class _CatalogedEvent(DomainEvent):
    """Internal mixin: typed event class with a stable name + factory.

    We deliberately *do not* add fields — the envelope already carries
    ``name``/``schema_version``/``context``. The subclass exists so the
    catalogue is type-checkable and discoverable via ``__subclasses__``.
    """

    NAME: ClassVar[str] = ""
    SCHEMA_VERSION: ClassVar[int] = 1
    CONTEXT: ClassVar[str] = ""

    @classmethod
    def make(
        cls,
        *,
        run_id: RunId | None,
        payload: Mapping[str, Any],
        causation_id: UUID | None = None,
    ) -> _CatalogedEvent:
        """Construct a fully-populated event of this concrete type.

        Returns an instance of ``cls`` (a :class:`DomainEvent` subclass), so
        downstream code can both pattern-match on type and serialise via
        :meth:`DomainEvent.to_dict`.
        """
        if not cls.NAME:
            raise NotImplementedError(
                f"{cls.__name__} must define a class-level NAME"
            )
        if not cls.CONTEXT:
            raise NotImplementedError(
                f"{cls.__name__} must define a class-level CONTEXT"
            )
        return cls(
            event_id=uuid4(),
            run_id=run_id,
            name=cls.NAME,
            schema_version=cls.SCHEMA_VERSION,
            occurred_at=datetime.now(UTC),
            context=cls.CONTEXT,
            payload=dict(payload),
            causation_id=causation_id,
        )


# ---------------------------------------------------------------------------
# 3.1 Intent Interpretation
# ---------------------------------------------------------------------------


class IntentSubmitted(_CatalogedEvent):
    NAME = "IntentSubmitted"
    CONTEXT = "intent"


class LlmInvocationStarted(_CatalogedEvent):
    NAME = "LlmInvocationStarted"
    CONTEXT = "intent"


class LlmInvocationSucceeded(_CatalogedEvent):
    NAME = "LlmInvocationSucceeded"
    CONTEXT = "intent"


class LlmInvocationFailed(_CatalogedEvent):
    NAME = "LlmInvocationFailed"
    CONTEXT = "intent"


class DemoModeEngaged(_CatalogedEvent):
    NAME = "DemoModeEngaged"
    CONTEXT = "intent"


class CodegenRequestParsed(_CatalogedEvent):
    NAME = "CodegenRequestParsed"
    CONTEXT = "intent"


class CodegenRequestRejected(_CatalogedEvent):
    NAME = "CodegenRequestRejected"
    CONTEXT = "intent"


# ---------------------------------------------------------------------------
# 3.2 API Modelling
# ---------------------------------------------------------------------------


class IRConstructed(_CatalogedEvent):
    NAME = "IRConstructed"
    CONTEXT = "modelling"


class IRRejected(_CatalogedEvent):
    NAME = "IRRejected"
    CONTEXT = "modelling"


# ---------------------------------------------------------------------------
# 3.3 Artifact Generation
# ---------------------------------------------------------------------------


class GenerationPlanned(_CatalogedEvent):
    NAME = "GenerationPlanned"
    CONTEXT = "generation"


class ArtifactRendered(_CatalogedEvent):
    NAME = "ArtifactRendered"
    CONTEXT = "generation"


class ArtifactPostProcessed(_CatalogedEvent):
    NAME = "ArtifactPostProcessed"
    CONTEXT = "generation"


class ArtifactGenerated(_CatalogedEvent):
    NAME = "ArtifactGenerated"
    CONTEXT = "generation"


class ArtifactBundleSealed(_CatalogedEvent):
    NAME = "ArtifactBundleSealed"
    CONTEXT = "generation"


class ArtifactGenerationFailed(_CatalogedEvent):
    NAME = "ArtifactGenerationFailed"
    CONTEXT = "generation"


# ---------------------------------------------------------------------------
# 3.4 Cluster Provisioning
# ---------------------------------------------------------------------------


class PrerequisiteCheckSucceeded(_CatalogedEvent):
    NAME = "PrerequisiteCheckSucceeded"
    CONTEXT = "cluster"


class PrerequisiteCheckFailed(_CatalogedEvent):
    NAME = "PrerequisiteCheckFailed"
    CONTEXT = "cluster"


class ClusterCreationStarted(_CatalogedEvent):
    NAME = "ClusterCreationStarted"
    CONTEXT = "cluster"


class ClusterCreationSucceeded(_CatalogedEvent):
    NAME = "ClusterCreationSucceeded"
    CONTEXT = "cluster"


class ClusterCreationFailed(_CatalogedEvent):
    NAME = "ClusterCreationFailed"
    CONTEXT = "cluster"


class CrdApplied(_CatalogedEvent):
    NAME = "CrdApplied"
    CONTEXT = "cluster"


class InstanceApplied(_CatalogedEvent):
    NAME = "InstanceApplied"
    CONTEXT = "cluster"


class DeploymentVerified(_CatalogedEvent):
    NAME = "DeploymentVerified"
    CONTEXT = "cluster"


class DeploymentVerificationFailed(_CatalogedEvent):
    NAME = "DeploymentVerificationFailed"
    CONTEXT = "cluster"


# ---------------------------------------------------------------------------
# 3.5 User Interaction
# ---------------------------------------------------------------------------


class CommandStarted(_CatalogedEvent):
    NAME = "CommandStarted"
    CONTEXT = "user_interaction"


class CommandSucceeded(_CatalogedEvent):
    NAME = "CommandSucceeded"
    CONTEXT = "user_interaction"


class CommandFailed(_CatalogedEvent):
    NAME = "CommandFailed"
    CONTEXT = "user_interaction"


class RenderModeChosen(_CatalogedEvent):
    NAME = "RenderModeChosen"
    CONTEXT = "user_interaction"


# ---------------------------------------------------------------------------
# 3.6 Orchestration / cross-cutting
# ---------------------------------------------------------------------------


class RunStarted(_CatalogedEvent):
    NAME = "RunStarted"
    CONTEXT = "orchestrator"


class StageStarted(_CatalogedEvent):
    NAME = "StageStarted"
    CONTEXT = "orchestrator"


class StageSucceeded(_CatalogedEvent):
    NAME = "StageSucceeded"
    CONTEXT = "orchestrator"


class StageFailed(_CatalogedEvent):
    NAME = "StageFailed"
    CONTEXT = "orchestrator"


class CompensationApplied(_CatalogedEvent):
    NAME = "CompensationApplied"
    CONTEXT = "orchestrator"


class RunSucceeded(_CatalogedEvent):
    NAME = "RunSucceeded"
    CONTEXT = "orchestrator"


class RunFailed(_CatalogedEvent):
    NAME = "RunFailed"
    CONTEXT = "orchestrator"


# Public catalogue --- used by ``__init__`` re-exports and tests.
ALL_EVENT_TYPES: tuple[type[_CatalogedEvent], ...] = (
    # intent
    IntentSubmitted,
    LlmInvocationStarted,
    LlmInvocationSucceeded,
    LlmInvocationFailed,
    DemoModeEngaged,
    CodegenRequestParsed,
    CodegenRequestRejected,
    # modelling
    IRConstructed,
    IRRejected,
    # generation
    GenerationPlanned,
    ArtifactRendered,
    ArtifactPostProcessed,
    ArtifactGenerated,
    ArtifactBundleSealed,
    ArtifactGenerationFailed,
    # cluster
    PrerequisiteCheckSucceeded,
    PrerequisiteCheckFailed,
    ClusterCreationStarted,
    ClusterCreationSucceeded,
    ClusterCreationFailed,
    CrdApplied,
    InstanceApplied,
    DeploymentVerified,
    DeploymentVerificationFailed,
    # user interaction
    CommandStarted,
    CommandSucceeded,
    CommandFailed,
    RenderModeChosen,
    # orchestrator
    RunStarted,
    StageStarted,
    StageSucceeded,
    StageFailed,
    CompensationApplied,
    RunSucceeded,
    RunFailed,
)
