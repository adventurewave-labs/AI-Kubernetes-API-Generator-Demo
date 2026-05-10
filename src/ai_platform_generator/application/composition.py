"""Composition root.

The single place where concrete adapters are wired into the application
layer. See ``docs/ddd/06-application-services.md`` §7. Phase 4 will load
``AppConfig`` from the environment; for now the function accepts a
config and returns a fully-wired
:class:`GenerationOrchestrator`.

This Wave wires **fakes** so callers can drive a run without external
dependencies — a real ``OpenRouterLlmAdapter`` and
``KindClusterRuntime`` will replace them in Wave 3.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ai_platform_generator.adapters.clock.system import SystemClock
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
    GenerationOrchestrator,
)
from ai_platform_generator.application.services import (
    ApiModellingService,
    ArtifactGenerationService,
    ClusterProvisioningService,
    IntentInterpretationService,
)


class AppConfig(BaseModel):
    """Minimal configuration model for the composition root.

    Phase 4 will extend this with env-loaded fields (``OPENROUTER_API_KEY``,
    ``OTEL_EXPORTER``, ``LOG_FORMAT``, ...).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_root: Path = Field(default_factory=lambda: Path.cwd() / "generated")
    cluster_name: str = "ai-platform-demo"
    log_format: str = "tty"


def build_orchestrator(config: AppConfig | None = None) -> GenerationOrchestrator:
    """Wire fakes into a runnable :class:`GenerationOrchestrator`.

    The function deliberately does *not* read environment variables yet —
    Wave 4 introduces ``ChainSecretProvider`` and the live adapters.
    """
    config = config or AppConfig()

    clock = SystemClock()
    sink = RecordingSink()
    llm = FakeLlmAdapter()
    runtime = FakeClusterRuntime()
    artifact_repo = InMemoryArtifactRepository()
    runs_repo = InMemoryRunRepository()

    interpret = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
        allow_demo_mode=True,
    )
    model = ApiModellingService(events=sink)
    generate = ArtifactGenerationService(
        repo=artifact_repo,
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
        runs=runs_repo,
        events=sink,
        clock=clock,
        llm=llm,
        runtime=runtime,
    )


__all__ = ["AppConfig", "build_orchestrator"]
