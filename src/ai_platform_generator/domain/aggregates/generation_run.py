"""GenerationRun entity (mutable lifecycle owner).

See ``docs/ddd/04-tactical-design.md`` section 3.1 for the contract.

Unlike the other aggregates in this package, ``GenerationRun`` is
mutable — it owns the run's *state machine*. The orchestrator
application service (Agent F) is the only caller permitted to drive
state transitions. Direct field mutation (other than through
:meth:`GenerationRun.transition_to`, :meth:`attach_request`,
:meth:`attach_ir`, :meth:`attach_bundle`, and :meth:`attach_deployment`)
is unsupported; the field setters intentionally exist on the entity
so the orchestrator does not have to reach into private attributes.

The ``Deployment`` value defined here is a stub — the full Cluster
Provisioning context will replace it once that bounded context lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ai_platform_generator.domain.aggregates.artifact_bundle import ArtifactBundle
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import OpenAPIDocument
from ai_platform_generator.domain.errors.domain_validation import DomainValidationError
from ai_platform_generator.domain.values import Intent, RunId


class InvalidGenerationRun(DomainValidationError):
    """The :class:`GenerationRun` entity failed an invariant check."""

    code = "E_DOMAIN_INVALID_GENERATION_RUN"


class IllegalRunTransition(DomainValidationError):
    """An attempted run-state transition is not permitted."""

    code = "E_DOMAIN_ILLEGAL_RUN_TRANSITION"


# ---------------------------------------------------------------------------
# RunState state machine
# ---------------------------------------------------------------------------


class RunState(StrEnum):
    """The possible lifecycle states of a generation run.

    Transitions are gated by :meth:`GenerationRun.transition_to`:

    .. code-block:: text

       PENDING -> INTERPRETING -> MODELLING -> GENERATING -> PERSISTING -> SUCCEEDED
                                                                           |
                                                                           v
                                                  PROVISIONING -> VERIFYING -> SUCCEEDED
       any -> FAILED

    ``PERSISTING`` may transition either to ``SUCCEEDED`` (no
    cluster step requested) or ``PROVISIONING`` (cluster step
    requested), and ``VERIFYING`` always lands in ``SUCCEEDED`` on
    success. Anything can transition to ``FAILED``.
    """

    PENDING = "pending"
    INTERPRETING = "interpreting"
    MODELLING = "modelling"
    GENERATING = "generating"
    PERSISTING = "persisting"
    PROVISIONING = "provisioning"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_ALLOWED: dict[RunState, frozenset[RunState]] = {
    RunState.PENDING: frozenset({RunState.INTERPRETING, RunState.FAILED}),
    RunState.INTERPRETING: frozenset({RunState.MODELLING, RunState.FAILED}),
    RunState.MODELLING: frozenset({RunState.GENERATING, RunState.FAILED}),
    RunState.GENERATING: frozenset({RunState.PERSISTING, RunState.FAILED}),
    RunState.PERSISTING: frozenset(
        {RunState.SUCCEEDED, RunState.PROVISIONING, RunState.FAILED}
    ),
    RunState.PROVISIONING: frozenset({RunState.VERIFYING, RunState.FAILED}),
    RunState.VERIFYING: frozenset({RunState.SUCCEEDED, RunState.FAILED}),
    RunState.SUCCEEDED: frozenset(),
    RunState.FAILED: frozenset(),
}


# ---------------------------------------------------------------------------
# Deployment stub
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Deployment:
    """Stub for the Cluster Provisioning context's ``Deployment`` entity.

    The full deployment type will be defined in
    ``domain/aggregates/deployment.py`` (or equivalent) when the cluster
    provisioning context lands. For now we only need enough of the shape
    for ``GenerationRun`` to track the deployment outcome.
    """

    id: UUID
    cluster_name: str
    crd_applied: bool = False
    instance_applied: bool = False
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise InvalidGenerationRun(
                f"Deployment.id must be a UUID, got {type(self.id)!r}"
            )
        if not isinstance(self.cluster_name, str) or not self.cluster_name.strip():
            raise InvalidGenerationRun(
                "Deployment.cluster_name must be a non-blank str, got "
                f"{self.cluster_name!r}"
            )


# ---------------------------------------------------------------------------
# GenerationRun entity
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GenerationRun:
    """The mutable lifecycle owner of a single generation run.

    Identity is :attr:`id`. The remaining fields evolve as the run
    progresses through the pipeline.
    """

    id: RunId
    started_at: datetime
    intent: Intent
    request: CodegenRequest | None = None
    ir: OpenAPIDocument | None = None
    bundle: ArtifactBundle | None = None
    deployment: Deployment | None = None
    state: RunState = field(default=RunState.PENDING)

    def __post_init__(self) -> None:
        if not isinstance(self.id, RunId):
            raise InvalidGenerationRun(
                f"id must be a RunId, got {type(self.id)!r}"
            )
        if not isinstance(self.started_at, datetime):
            raise InvalidGenerationRun(
                f"started_at must be a datetime, got {type(self.started_at)!r}"
            )
        if not isinstance(self.intent, Intent):
            raise InvalidGenerationRun(
                f"intent must be an Intent, got {type(self.intent)!r}"
            )
        if self.request is not None and not isinstance(self.request, CodegenRequest):
            raise InvalidGenerationRun(
                f"request must be a CodegenRequest or None, got {type(self.request)!r}"
            )
        if self.ir is not None and not isinstance(self.ir, OpenAPIDocument):
            raise InvalidGenerationRun(
                f"ir must be an OpenAPIDocument or None, got {type(self.ir)!r}"
            )
        if self.bundle is not None and not isinstance(self.bundle, ArtifactBundle):
            raise InvalidGenerationRun(
                f"bundle must be an ArtifactBundle or None, got {type(self.bundle)!r}"
            )
        if self.deployment is not None and not isinstance(self.deployment, Deployment):
            raise InvalidGenerationRun(
                f"deployment must be a Deployment or None, got {type(self.deployment)!r}"
            )
        if not isinstance(self.state, RunState):
            raise InvalidGenerationRun(
                f"state must be a RunState, got {type(self.state)!r}"
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def transition_to(self, new_state: RunState) -> None:
        """Transition to ``new_state``, raising on illegal transitions.

        Raises
        ------
        IllegalRunTransition
            If the transition from :attr:`state` to ``new_state`` is
            not permitted by the state machine.
        ValueError
            If ``new_state`` is not a :class:`RunState`. (Kept for
            backwards compatibility with callers that assert
            ``ValueError``.)
        """
        if not isinstance(new_state, RunState):
            raise ValueError(f"new_state must be a RunState, got {type(new_state)!r}")
        allowed = _ALLOWED.get(self.state, frozenset())
        if new_state not in allowed:
            raise IllegalRunTransition(
                f"illegal run-state transition {self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    # ------------------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------------------
    def attach_request(self, request: CodegenRequest) -> None:
        if not isinstance(request, CodegenRequest):
            raise InvalidGenerationRun(
                f"request must be a CodegenRequest, got {type(request)!r}"
            )
        self.request = request

    def attach_ir(self, ir: OpenAPIDocument) -> None:
        if not isinstance(ir, OpenAPIDocument):
            raise InvalidGenerationRun(
                f"ir must be an OpenAPIDocument, got {type(ir)!r}"
            )
        self.ir = ir

    def attach_bundle(self, bundle: ArtifactBundle) -> None:
        if not isinstance(bundle, ArtifactBundle):
            raise InvalidGenerationRun(
                f"bundle must be an ArtifactBundle, got {type(bundle)!r}"
            )
        self.bundle = bundle

    def attach_deployment(self, deployment: Deployment) -> None:
        if not isinstance(deployment, Deployment):
            raise InvalidGenerationRun(
                f"deployment must be a Deployment, got {type(deployment)!r}"
            )
        self.deployment = deployment

    # ------------------------------------------------------------------
    # Equality / identity
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GenerationRun):
            return NotImplemented
        # Identity-based equality: a run is the same run iff its id
        # matches (entities have identity, not value semantics).
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


__all__ = [
    "Deployment",
    "GenerationRun",
    "IllegalRunTransition",
    "InvalidGenerationRun",
    "RunState",
]
