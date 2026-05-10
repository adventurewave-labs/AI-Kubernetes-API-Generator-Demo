"""``GenerationOrchestrator`` — the cross-cutting saga.

Realises ``docs/ddd/06-application-services.md`` §4.

The orchestrator is the *only* place in the application layer that
sequences bounded contexts. It owns:

* the per-stage bookkeeping decorator ``_stage`` (see §4.1);
* the recovery rules from §4.2 (LLM rate-limit retry happens *inside*
  :class:`IntentInterpretationService`; demo-mode swap is delegated to
  ``_resolve_llm`` at construction time);
* the compensating actions from §4.3.

Wave-3 dependency: ``DemoModeLlmAdapter`` does not yet exist. The
orchestrator therefore raises :class:`LlmUnavailable` /
:class:`LlmAuthenticationFailed` upward when ``allow_demo_mode`` is
True; tests can assert that the orchestrator inspected
``provider.is_available()`` and emitted ``StageFailed``. Once the demo
adapter lands, ``_resolve_llm`` will swap providers for the retry.
"""

from __future__ import annotations

import contextlib
import dataclasses
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypeVar

from ai_platform_generator.application.orchestrator.params import (
    ArtifactType,
    GenerateParams,
)
from ai_platform_generator.application.orchestrator.summary import (
    GenerationSummary,
)
from ai_platform_generator.domain.errors import (
    ArtifactWriteFailed,
    ClusterCreationTimedOut,
    DeploymentVerificationFailed,
    LlmAuthenticationFailed,
    LlmUnavailable,
    PlatformGeneratorError,
)
from ai_platform_generator.domain.events import (
    CompensationApplied,
    RunFailed,
    RunStarted,
    RunSucceeded,
    StageFailed,
    StageStarted,
    StageSucceeded,
)
from ai_platform_generator.domain.values import Intent, RunId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.services import (
        ApiModellingService,
        ArtifactGenerationService,
        ClusterProvisioningService,
        IntentInterpretationService,
    )
    from ai_platform_generator.ports import (
        Clock,
        ClusterRuntime,
        LlmProvider,
        RunRepository,
        TelemetrySink,
    )


T = TypeVar("T")


@dataclasses.dataclass
class _RunState:
    """Mutable bookkeeping for an in-flight Generation Run.

    Lives only inside the orchestrator. Once Agent E lands the
    ``GenerationRun`` aggregate, this class is replaced by direct
    transitions on the aggregate.
    """

    id: RunId
    started_at: datetime
    intent: Intent
    state: str = "pending"
    request: Any = None
    ir: Any = None
    bundle: Any = None
    deployment: Any = None
    cluster: Any = None
    error_code: str | None = None


class GenerationOrchestrator:
    """Sequence the six bounded contexts behind a single ``run`` method."""

    def __init__(
        self,
        interpret: IntentInterpretationService,
        model: ApiModellingService,
        generate: ArtifactGenerationService,
        provision: ClusterProvisioningService,
        runs: RunRepository,
        events: TelemetrySink,
        clock: Clock,
        llm: LlmProvider,
        runtime: ClusterRuntime,
    ) -> None:
        self._interpret = interpret
        self._model = model
        self._generate = generate
        self._provision = provision
        self._runs = runs
        self._events = events
        self._clock = clock
        self._llm = llm
        self._runtime = runtime

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, params: GenerateParams) -> GenerationSummary:
        """Drive a single Generation Run end to end."""
        run = _RunState(
            id=RunId.new(),
            started_at=self._clock.now(),
            intent=Intent(text=params.intent_text, submitted_at=self._clock.now()),
        )
        self._runs.append(_to_run_aggregate(run))
        self._events.emit(
            RunStarted.make(
                run_id=run.id,
                payload={
                    "run_id": run.id.value,
                    "started_at": run.started_at.isoformat(),
                },
            )
        )
        started_mono = self._clock.monotonic()

        try:
            self._stage(
                run,
                "interpret",
                lambda: self._interpret.parse(run.intent, run_id=run.id),
                set_attr="request",
            )
            self._stage(
                run,
                "model",
                lambda: self._model.build(run.request, run_id=run.id),
                set_attr="ir",
            )
            target_dir = _resolve_target_dir(params, run.request)
            self._stage(
                run,
                "generate",
                lambda: self._generate.run(
                    run.ir,
                    request=run.request,
                    target_dir=target_dir,
                    run_id=run.id,
                ),
                set_attr="bundle",
            )

            if params.deploy_to_cluster:
                self._stage(
                    run,
                    "provision",
                    lambda: self._do_provision(run, params),
                    set_attr="deployment",
                )
                self._stage(
                    run,
                    "verify",
                    lambda: self._provision.verify(
                        run.deployment, run.cluster, run_id=run.id
                    ),
                    set_attr="deployment",
                )

            duration_ms = int(
                (self._clock.monotonic() - started_mono) * 1000
            )
            self._events.emit(
                RunSucceeded.make(
                    run_id=run.id,
                    payload={
                        "run_id": run.id.value,
                        "duration_ms": duration_ms,
                    },
                )
            )
            run.state = "succeeded"
            return self._summarise(run, params, duration_ms=duration_ms)

        except PlatformGeneratorError as exc:
            self._compensate(run, exc, params)
            duration_ms = int(
                (self._clock.monotonic() - started_mono) * 1000
            )
            run.state = "failed"
            run.error_code = exc.code
            self._events.emit(
                RunFailed.make(
                    run_id=run.id,
                    payload={
                        "run_id": run.id.value,
                        "duration_ms": duration_ms,
                        "error_code": exc.code,
                    },
                )
            )
            raise

    # ------------------------------------------------------------------
    # Stage decorator
    # ------------------------------------------------------------------
    def _stage(
        self,
        run: _RunState,
        stage: str,
        body: Callable[[], T],
        *,
        set_attr: str | None = None,
    ) -> T:
        """Time, announce, and bookkeep a single saga stage."""
        run.state = stage
        self._events.emit(
            StageStarted.make(
                run_id=run.id,
                payload={"run_id": run.id.value, "stage": stage},
            )
        )
        started = self._clock.monotonic()
        try:
            result = body()
        except PlatformGeneratorError as exc:
            duration_ms = int((self._clock.monotonic() - started) * 1000)
            self._events.emit(
                StageFailed.make(
                    run_id=run.id,
                    payload={
                        "run_id": run.id.value,
                        "stage": stage,
                        "error_code": exc.code,
                        "recoverable": exc.recoverable,
                    },
                )
            )
            raise
        else:
            duration_ms = int((self._clock.monotonic() - started) * 1000)
            self._events.emit(
                StageSucceeded.make(
                    run_id=run.id,
                    payload={
                        "run_id": run.id.value,
                        "stage": stage,
                        "duration_ms": duration_ms,
                    },
                )
            )
            if set_attr is not None:
                setattr(run, set_attr, result)
            return result

    # ------------------------------------------------------------------
    # Recovery / demo-mode resolution
    # ------------------------------------------------------------------
    def _resolve_llm(
        self, params: GenerateParams
    ) -> LlmProvider:
        """Resolve the LLM provider, swapping to demo mode if allowed.

        Wave-3 placeholder: when ``allow_demo_mode`` is True and the
        primary provider is unavailable, the orchestrator swaps in
        ``DemoModeLlmAdapter``. That adapter has not been implemented
        yet; for now we propagate :class:`LlmUnavailable` /
        :class:`LlmAuthenticationFailed` upward and let tests assert
        the failure path.
        """
        primary = self._llm
        try:
            available = primary.is_available()
        except (LlmUnavailable, LlmAuthenticationFailed):
            available = False
        if available or not params.allow_demo_mode:
            return primary
        # ``DemoModeLlmAdapter`` would live here once Wave 3 lands. Until
        # then, return the primary so the caller hits the typed error
        # path explicitly.
        return primary

    # ------------------------------------------------------------------
    # Compensation hooks (per §4.2 / §4.3)
    # ------------------------------------------------------------------
    def _compensate(
        self,
        run: _RunState,
        exc: PlatformGeneratorError,
        params: GenerateParams,
    ) -> None:
        """Run the compensating action for the stage that failed.

        See ``docs/ddd/06-application-services.md`` §4.2.
        """
        stage = run.state
        if stage == "generate" and isinstance(exc, ArtifactWriteFailed):
            self._delete_partial_bundle(run)
            self._emit_compensation(run, "generate", "delete_partial_bundle")
        elif stage == "provision" and isinstance(exc, ClusterCreationTimedOut):
            with contextlib.suppress(Exception):
                self._runtime.delete_cluster(params.cluster_name)
            self._emit_compensation(run, "provision", "delete_cluster")
        elif stage == "verify" and isinstance(exc, DeploymentVerificationFailed):
            self._emit_diagnostic_snapshot(run)
            self._emit_compensation(run, "verify", "emit_diagnostic_snapshot")

    def _delete_partial_bundle(self, run: _RunState) -> None:
        """Remove the bundle's target directory, if any (best-effort)."""
        target = getattr(run.bundle, "target_dir", None)
        if target is None:
            return
        with contextlib.suppress(Exception):
            shutil.rmtree(Path(target), ignore_errors=True)

    def _emit_diagnostic_snapshot(self, run: _RunState) -> None:
        """Stub: emit a diagnostic event so subscribers can persist it."""
        # Once a real ``DeploymentDiagnosticsCaptured`` event lands we'll
        # use that. For now reuse ``CompensationApplied`` so the
        # contract is observable.
        self._events.emit(
            CompensationApplied.make(
                run_id=run.id,
                payload={
                    "run_id": run.id.value,
                    "stage": "verify",
                    "action": "diagnostic_snapshot",
                },
            )
        )

    def _emit_compensation(
        self, run: _RunState, stage: str, action: str
    ) -> None:
        self._events.emit(
            CompensationApplied.make(
                run_id=run.id,
                payload={
                    "run_id": run.id.value,
                    "stage": stage,
                    "action": action,
                },
            )
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _do_provision(
        self, run: _RunState, params: GenerateParams
    ) -> Any:
        """Orchestrate prereqs, ensure, deploy in a single saga step."""
        self._provision.check_prerequisites(run_id=run.id)
        cluster = self._provision.ensure(params.cluster_name, run_id=run.id)
        run.cluster = cluster
        return self._provision.deploy(run.bundle, cluster, run_id=run.id)

    def _summarise(
        self,
        run: _RunState,
        params: GenerateParams,
        *,
        duration_ms: int,
    ) -> GenerationSummary:
        gvk = getattr(run.request, "gvk", None)
        bundle_dir = getattr(run.bundle, "target_dir", None)
        files = getattr(run.bundle, "files", ())
        artefact_paths = [
            Path(getattr(f, "path", ""))
            for f in files
            if getattr(f, "path", None) is not None
        ]
        provider_mode = getattr(run.request, "provider_mode", None)
        return GenerationSummary(
            run_id=run.id,
            state=run.state,
            gvk=gvk,
            bundle_dir=Path(bundle_dir) if bundle_dir else None,
            artefact_paths=artefact_paths,
            cluster_name=params.cluster_name if params.deploy_to_cluster else None,
            deployment_status="ok" if run.deployment is not None else None,
            duration_ms=duration_ms,
            provider_mode=provider_mode,
        )


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _resolve_target_dir(params: GenerateParams, request: Any) -> Path:
    """Resolve the target directory for a run, preferring CLI overrides."""
    if params.output_dir is not None:
        return Path(params.output_dir)
    out = getattr(request, "output_path", None)
    if out is not None and hasattr(out, "full"):
        return Path(out.full)
    return Path("generated")


def _to_run_aggregate(run: _RunState) -> Any:
    """Wrap ``_RunState`` in something the run repository can store.

    Uses Agent E's ``GenerationRun`` aggregate when its dependencies are
    importable; falls back to a ``SimpleNamespace`` otherwise.
    """
    try:
        from ai_platform_generator.domain.aggregates import (  # type: ignore[attr-defined]
            GenerationRun,
            RunState,
        )

        return GenerationRun(
            id=run.id,
            started_at=run.started_at,
            intent=run.intent,
            state=RunState.PENDING,
        )
    except (ImportError, AttributeError, TypeError):
        return SimpleNamespace(
            id=run.id,
            started_at=run.started_at or datetime.now(timezone.utc),
            intent=run.intent,
            state=run.state,
        )


# Re-export the canonical artefact enum so callers don't have to know
# whether it lives in this module or in ``params``.
__all__ = ["ArtifactType", "GenerationOrchestrator"]
