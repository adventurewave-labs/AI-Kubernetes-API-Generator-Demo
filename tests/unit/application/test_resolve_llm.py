"""Unit tests for :meth:`GenerationOrchestrator._resolve_llm`.

Per ADR-0009 the orchestrator must wrap a non-fallback primary into a
:class:`FallbackLlmProvider` so a transient ``LlmUnavailable`` /
``LlmAuthenticationFailed`` engages demo mode rather than failing the
run. A pre-wrapped primary must be honoured verbatim (no double-wrap).
"""

from __future__ import annotations

from typing import Any

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.llm.demo_mode import DemoModeLlmAdapter
from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
from ai_platform_generator.adapters.llm.fallback import FallbackLlmProvider
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


def _build_orchestrator(llm: Any) -> GenerationOrchestrator:
    sink = RecordingSink()
    clock = FrozenClock()
    runtime = FakeClusterRuntime()
    interpret = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
    )
    model = ApiModellingService(events=sink)
    generate = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=sink,
        clock=clock,
        generators=[],
    )
    provision = ClusterProvisioningService(
        runtime=runtime, events=sink, clock=clock
    )
    return GenerationOrchestrator(
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


def _params(*, allow_demo_mode: bool = True) -> GenerateParams:
    return GenerateParams(
        intent_text="Build a Foo CRD",
        deploy_to_cluster=False,
        allow_demo_mode=allow_demo_mode,
    )


def test_resolve_llm_wraps_primary_in_fallback_provider() -> None:
    primary = FakeLlmAdapter()
    orc = _build_orchestrator(primary)

    resolved = orc._resolve_llm(_params())
    assert isinstance(resolved, FallbackLlmProvider)
    assert resolved.primary is primary
    assert isinstance(resolved.fallback, DemoModeLlmAdapter)


def test_resolve_llm_passes_through_existing_fallback() -> None:
    primary = FakeLlmAdapter()
    pre_wrapped = FallbackLlmProvider(
        primary=primary, fallback=DemoModeLlmAdapter()
    )
    orc = _build_orchestrator(pre_wrapped)

    resolved = orc._resolve_llm(_params())
    assert resolved is pre_wrapped


def test_resolve_llm_returns_primary_when_demo_disallowed() -> None:
    primary = FakeLlmAdapter()
    orc = _build_orchestrator(primary)

    resolved = orc._resolve_llm(_params(allow_demo_mode=False))
    assert resolved is primary
