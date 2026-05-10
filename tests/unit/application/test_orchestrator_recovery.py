"""Recovery-rule tests for :class:`GenerationOrchestrator`.

Covers each row in ``docs/ddd/06-application-services.md`` §4.2:

* Interpret + ``LlmRateLimited`` → retry-with-backoff inside the
  intent-interpretation service (the orchestrator just observes
  ``LlmInvocationFailed`` followed by recovery).
* Interpret + ``LlmUnavailable`` / ``LlmAuthenticationFailed`` →
  raised upward (demo-mode swap is a Wave-3 dependency).
* Generate + any → terminal (orchestrator does not compensate for
  generator failures other than ``ArtifactWriteFailed``; documented).
* Persist + ``ArtifactWriteFailed`` → ``_delete_partial_bundle`` runs
  and ``CompensationApplied`` is emitted.
* Provision + ``ClusterCreationTimedOut`` → ``runtime.delete_cluster``
  is called.
* Verify + ``DeploymentVerificationFailed`` → diagnostic snapshot
  ``CompensationApplied`` event emitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
from ai_platform_generator.adapters.repo.in_memory import (
    InMemoryArtifactRepository,
)
from ai_platform_generator.adapters.run_repository.in_memory import (
    InMemoryRunRepository,
)
from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime
from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.application.orchestrator import (
    GenerateParams,
    GenerationOrchestrator,
)
from ai_platform_generator.application.services import (
    ApiModellingService,
    ArtifactGenerationService,
    ClusterProvisioningService,
    IntentInterpretationService,
)
from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactType,
    RenderedArtifact,
)
from ai_platform_generator.domain.errors import (
    ArtifactWriteFailed,
    ClusterCreationTimedOut,
    DeploymentVerificationFailed,
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmUnavailable,
)
from ai_platform_generator.domain.values import Checksum

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_CANNED = {
    "group": "platform.example.com",
    "version": "v1alpha1",
    "kind": "Foo",
    "spec_properties": {"replicas": {"type": "integer"}},
    "output_dir": "out",
    "description": "A foo.",
}


class _FailingLlm:
    """Provider that always raises ``exc`` on ``complete_json``."""

    name = "failing"
    model = "failing-1"
    mode = "live"

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def is_available(self) -> bool:
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Any = None,
        timeout_s: float = 60.0,
    ) -> dict[str, Any]:
        raise self._exc


class _RateLimitedThenOkLlm:
    name = "rl"
    model = "rl-1"
    mode = "live"

    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete_json(self, *args: Any, **kw: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls < 2:
            raise LlmRateLimited("slow down")
        return _CANNED


def _build(
    llm: Any = None,
    *,
    runtime: Any = None,
    generators: list[Any] | None = None,
    sleep: Any = lambda _s: None,
) -> tuple[GenerationOrchestrator, RecordingSink, Any]:
    sink = RecordingSink()
    clock = FrozenClock()
    llm = llm if llm is not None else FakeLlmAdapter(responses=[_CANNED])
    runtime = runtime if runtime is not None else FakeClusterRuntime()
    interpret = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
        sleep=sleep,
    )
    model = ApiModellingService(events=sink)
    generate = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=sink,
        clock=clock,
        generators=generators or [],
    )
    provision = ClusterProvisioningService(
        runtime=runtime, events=sink, clock=clock, sleep=sleep
    )
    orchestrator = GenerationOrchestrator(
        interpret=interpret,
        model=model,
        generate=generate,
        provision=provision,
        runs=InMemoryRunRepository(),
        events=sink,
        clock=clock,
        llm=llm,
        runtime=runtime,
    )
    return orchestrator, sink, runtime


def _params(
    *,
    deploy: bool = False,
    output_dir: Path | None = None,
    allow_demo_mode: bool = True,
) -> GenerateParams:
    return GenerateParams(
        intent_text="A Foo with replicas",
        deploy_to_cluster=deploy,
        output_dir=output_dir,
        allow_demo_mode=allow_demo_mode,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_emits_full_stage_event_sequence(tmp_path) -> None:
    orc, sink, _ = _build()
    orc.run(_params(output_dir=tmp_path))

    sink.assert_events_in_order(
        "RunStarted",
        "StageStarted",  # interpret
        "StageSucceeded",
        "StageStarted",  # model
        "StageSucceeded",
        "StageStarted",  # generate
        "StageSucceeded",
        "RunSucceeded",
    )


# ---------------------------------------------------------------------------
# §4.2 row 1 — Interpret + LlmRateLimited → retry with backoff
# ---------------------------------------------------------------------------


def test_interpret_rate_limit_retries_and_succeeds(tmp_path) -> None:
    captured: list[float] = []
    llm = _RateLimitedThenOkLlm()
    orc, sink, _ = _build(llm=llm, sleep=captured.append)
    orc.run(_params(output_dir=tmp_path))

    assert llm.calls == 2
    assert captured == [2.0]  # one retry → one backoff
    assert sink.events_with_name("RunSucceeded")


# ---------------------------------------------------------------------------
# §4.2 row 2 — Interpret + LlmUnavailable / LlmAuthenticationFailed
# (demo-mode swap is a Wave-3 dependency; for now we re-raise.)
# ---------------------------------------------------------------------------


def test_interpret_unavailable_raises_and_emits_run_failed() -> None:
    orc, sink, _ = _build(llm=_FailingLlm(LlmUnavailable("net")))

    with pytest.raises(LlmUnavailable):
        orc.run(_params())

    sink.assert_events_in_order("RunStarted", "StageFailed", "RunFailed")


def test_interpret_auth_failed_raises_and_emits_run_failed() -> None:
    orc, sink, _ = _build(llm=_FailingLlm(LlmAuthenticationFailed("nope")))

    with pytest.raises(LlmAuthenticationFailed):
        orc.run(_params())

    sink.assert_events_in_order("RunStarted", "StageFailed", "RunFailed")


# ---------------------------------------------------------------------------
# §4.2 row 5 — Persist + ArtifactWriteFailed → delete_partial_bundle
# (the "Persist" stage is fused with "Generate" here because
#  ArtifactGenerationService.run does the persist; we trigger it via a
#  generator that raises ArtifactWriteFailed in ``generate``.)
# ---------------------------------------------------------------------------


class _RaisingGenerator:
    name = "raises"

    def generate(self, *args: Any, **kw: Any) -> Any:
        raise ArtifactWriteFailed("boom")

    def expected_paths(self, *args: Any, **kw: Any) -> list[Path]:
        return []


def test_generate_artifact_write_failed_runs_compensation(tmp_path) -> None:
    orc, sink, _ = _build(generators=[_RaisingGenerator()])
    with pytest.raises(ArtifactWriteFailed):
        orc.run(_params(output_dir=tmp_path))

    actions = [
        e.payload.get("action")
        for e in sink.events_with_name("CompensationApplied")
    ]
    assert "delete_partial_bundle" in actions
    assert sink.events_with_name("RunFailed")


# ---------------------------------------------------------------------------
# §4.2 row 7 — Provision + ClusterCreationTimedOut → kind delete cluster
# ---------------------------------------------------------------------------


def test_provision_timeout_runs_delete_cluster_compensation(tmp_path) -> None:
    runtime = FakeClusterRuntime()
    runtime.set_failure(
        "create_cluster", ClusterCreationTimedOut("create timed out")
    )
    orc, sink, _ = _build(runtime=runtime)

    with pytest.raises(ClusterCreationTimedOut):
        orc.run(_params(deploy=True, output_dir=tmp_path))

    actions = [
        e.payload.get("action")
        for e in sink.events_with_name("CompensationApplied")
    ]
    assert "delete_cluster" in actions
    # The compensation calls runtime.delete_cluster regardless of whether
    # the cluster ever existed — best-effort by design.
    assert any(c[0] == "delete_cluster" for c in runtime.calls)


# ---------------------------------------------------------------------------
# §4.2 row 9 — Verify + DeploymentVerificationFailed → diagnostic snapshot
# ---------------------------------------------------------------------------


def _crd_instance_generator() -> Any:
    """Generator producing one CRD + one Instance artefact."""

    crd = RenderedArtifact(
        path=Path("foo.crd.yaml"),
        payload=b"crd-bytes\n",
        mode=0o644,
        artefact_type=ArtifactType.CRD,
        checksum=Checksum.of(b"crd-bytes\n"),
    )
    inst = RenderedArtifact(
        path=Path("foo.instance.yaml"),
        payload=b"inst-bytes\n",
        mode=0o644,
        artefact_type=ArtifactType.INSTANCE,
        checksum=Checksum.of(b"inst-bytes\n"),
    )

    class _Gen:
        name = "fake"

        def generate(self, *args: Any, **kw: Any) -> list[RenderedArtifact]:
            return [crd, inst]

        def expected_paths(self, *args: Any, **kw: Any) -> list[Path]:
            return [crd.path, inst.path]

    return _Gen()


def test_verify_failure_emits_diagnostic_snapshot(tmp_path) -> None:
    """A failing ``verify`` step triggers the diagnostic compensation.

    Deploy must succeed end-to-end so the saga reaches the verify stage;
    we therefore wire a generator that produces a CRD + Instance bundle
    and make ``runtime.get`` succeed for the deploy polls but fail on
    the final verify-stage call.
    """
    from ai_platform_generator.ports.cluster_runtime import ResourceState

    class _LateFailRuntime(FakeClusterRuntime):
        def __init__(self) -> None:
            super().__init__()
            self._gets = 0

        def get(self, *args: Any, **kw: Any) -> ResourceState:
            self._gets += 1
            # Two deploy polls (CRD established, instance accessible)
            # then verify. Trip the failure on call #3.
            if self._gets >= 3:
                return ResourceState(
                    name="x",
                    namespace=None,
                    api_version="v1",
                    kind="Foo",
                    found=False,
                )
            return ResourceState(
                name="x",
                namespace=None,
                api_version="v1",
                kind="Foo",
                found=True,
            )

    orc, sink, _ = _build(
        runtime=_LateFailRuntime(),
        generators=[_crd_instance_generator()],
    )
    with pytest.raises(DeploymentVerificationFailed):
        orc.run(_params(deploy=True, output_dir=tmp_path))

    actions = [
        e.payload.get("action")
        for e in sink.events_with_name("CompensationApplied")
    ]
    assert "diagnostic_snapshot" in actions
