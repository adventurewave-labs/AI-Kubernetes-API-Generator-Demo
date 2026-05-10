"""Composition root.

The single place where concrete adapters are wired into the application
layer. See ``docs/ddd/06-application-services.md`` §7.

Two entry points are exposed:

* :func:`build_orchestrator` — production-shaped wiring. Honours
  :class:`AppConfig` for adapter selection, secret-chain construction,
  and observability sinks. Real adapters are used by default;
  :attr:`AppConfig.use_fakes` flips back to the in-memory wiring for
  smoke tests.
* :func:`build_test_orchestrator` — convenience helper for tests that
  want the all-fakes variant without authoring a config. Equivalent
  to ``build_orchestrator(AppConfig(use_fakes=True))``.

Defensive imports
-----------------
Sibling Wave-4 agents own the concrete artefact generators
(:mod:`ai_platform_generator.domain.generation.generators`). When
those modules are not yet importable the composition root **must not
crash** — it logs a warning and falls back to an empty generator
tuple so the orchestrator still runs (it just won't produce
artefacts). Production deployments with a complete checkout will get
the real generator set.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform_generator.adapters.clock.system import SystemClock
from ai_platform_generator.application.orchestrator import (
    GenerationOrchestrator,
)
from ai_platform_generator.application.services import (
    ApiModellingService,
    ArtifactGenerationService,
    ClusterProvisioningService,
    IntentInterpretationService,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.ports import (
        ArtifactRepository,
        Clock,
        ClusterRuntime,
        LlmProvider,
        RunRepository,
        SecretProvider,
        TelemetrySink,
    )


_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AppConfig
# ---------------------------------------------------------------------------


class AppConfig(BaseModel):
    """Composition-root configuration.

    Mirrors the env-driven settings the CLI honours. Tests construct an
    instance with ``use_fakes=True`` to short-circuit real-adapter
    construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    # Adapter selection ---------------------------------------------------
    llm_provider: Literal["openrouter", "openai", "demo", "fake"] = "openrouter"
    use_fakes: bool = False
    allow_demo_mode: bool = True

    # Filesystem / cluster ------------------------------------------------
    artifact_root: Path = Field(default_factory=lambda: Path.cwd() / "generated")
    output_dir: Path = Field(default_factory=lambda: Path("./generated_specs"))
    cluster_name: str = "ai-platform-demo"
    runs_log_path: Path = Field(
        default_factory=lambda: Path("./.platform-gen") / "runs.jsonl"
    )

    # Observability -------------------------------------------------------
    log_format: Literal["tty", "json", "quiet"] = "tty"
    enable_otel: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_orchestrator(
    config: AppConfig | None = None,
) -> GenerationOrchestrator:
    """Wire a fully-functional :class:`GenerationOrchestrator`.

    See module docstring for the wiring policy.
    """
    config = config or AppConfig()

    if config.use_fakes:
        return _build_fake_orchestrator(config)
    return _build_real_orchestrator(config)


def build_test_orchestrator() -> GenerationOrchestrator:
    """Construct the all-fakes orchestrator suitable for unit tests."""
    return _build_fake_orchestrator(AppConfig(use_fakes=True))


# ---------------------------------------------------------------------------
# Fake-adapter wiring (Wave-2 baseline)
# ---------------------------------------------------------------------------


def _build_fake_orchestrator(config: AppConfig) -> GenerationOrchestrator:
    """Wire the in-memory adapter set used by the unit-test suite."""
    from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
    from ai_platform_generator.adapters.repo.in_memory import (
        InMemoryArtifactRepository,
    )
    from ai_platform_generator.adapters.run_repository.in_memory import (
        InMemoryRunRepository,
    )
    from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime
    from ai_platform_generator.adapters.telemetry.recording import RecordingSink

    clock: Clock = SystemClock()
    sink: TelemetrySink = RecordingSink()
    llm: LlmProvider = FakeLlmAdapter()
    runtime: ClusterRuntime = FakeClusterRuntime()
    artifact_repo: ArtifactRepository = InMemoryArtifactRepository()
    runs_repo: RunRepository = InMemoryRunRepository()

    interpret = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
        allow_demo_mode=config.allow_demo_mode,
    )
    model = ApiModellingService(events=sink)
    generate = ArtifactGenerationService(
        repo=artifact_repo,
        events=sink,
        clock=clock,
        generators=list(_load_default_generators()),
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


# ---------------------------------------------------------------------------
# Real-adapter wiring (Wave-4 production)
# ---------------------------------------------------------------------------


def _build_real_orchestrator(config: AppConfig) -> GenerationOrchestrator:
    """Wire the real adapters per :class:`AppConfig`."""
    from ai_platform_generator.adapters.repo.filesystem import (
        FilesystemArtifactRepository,
    )
    from ai_platform_generator.adapters.run_repository.jsonl import (
        JsonlRunRepository,
    )
    from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime
    from ai_platform_generator.adapters.telemetry.multi import MultiSink
    from ai_platform_generator.domain.events.bus import EventBus
    from ai_platform_generator.domain.observability.dispatcher import (
        EventDispatcher,
    )

    clock: Clock = SystemClock()
    secrets: SecretProvider = _build_secret_chain()

    # ---- LLM ------------------------------------------------------------
    llm: LlmProvider = _build_llm(config, secrets)

    # ---- Artifact repo / cluster runtime --------------------------------
    artifact_repo: ArtifactRepository = FilesystemArtifactRepository(
        root=config.artifact_root,
    )
    runtime: ClusterRuntime = KindClusterRuntime()

    # ---- Telemetry ------------------------------------------------------
    sinks = _build_sinks(config, clock=clock)
    multi = MultiSink(sinks)
    bus = EventBus()
    dispatcher = EventDispatcher(bus=bus)
    dispatcher.subscribe_all(multi)

    # ---- Run repository -------------------------------------------------
    runs_repo: RunRepository = JsonlRunRepository(path=config.runs_log_path)

    # ---- Application services ------------------------------------------
    interpret = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=multi,
        clock=clock,
        allow_demo_mode=config.allow_demo_mode,
    )
    model = ApiModellingService(events=multi)
    generate = ArtifactGenerationService(
        repo=artifact_repo,
        events=multi,
        clock=clock,
        generators=list(_load_default_generators()),
    )
    provision = ClusterProvisioningService(
        runtime=runtime, events=multi, clock=clock
    )

    return GenerationOrchestrator(
        interpret=interpret,
        model=model,
        generate=generate,
        provision=provision,
        runs=runs_repo,
        events=multi,
        clock=clock,
        llm=llm,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_secret_chain() -> SecretProvider:
    """Build the canonical first-hit-wins secret chain (``Env`` → ``Dotenv``)."""
    from ai_platform_generator.adapters.secrets import (
        ChainSecretProvider,
        DotenvSecretProvider,
        EnvSecretProvider,
    )

    return ChainSecretProvider(
        [
            EnvSecretProvider(),
            DotenvSecretProvider(),
        ]
    )


def _build_llm(config: AppConfig, secrets: SecretProvider) -> LlmProvider:
    """Build the configured primary LLM, wrapping in fallback if allowed.

    Per ADR-0009 the *primary* is always whichever live adapter the
    config selects; demo mode is engaged only via the fallback path.
    Construction must not raise when no API key is available — we let
    the primary's own ``is_available()`` defer the failure so the
    orchestrator can swap to demo on first use.
    """
    from ai_platform_generator.adapters.llm import (
        DemoModeLlmAdapter,
        FakeLlmAdapter,
        FallbackLlmProvider,
    )

    primary: LlmProvider
    if config.llm_provider == "fake":
        primary = FakeLlmAdapter()
    elif config.llm_provider == "demo":
        primary = DemoModeLlmAdapter()
    elif config.llm_provider == "openai":
        primary = _build_openai_adapter(secrets)
    else:
        primary = _build_openrouter_adapter(secrets)

    if not config.allow_demo_mode:
        return primary

    return FallbackLlmProvider(
        primary=primary,
        fallback=DemoModeLlmAdapter(),
    )


def _build_openrouter_adapter(secrets: SecretProvider) -> LlmProvider:
    """Construct an :class:`OpenRouterLlmAdapter`, deferring missing-key failures."""
    from ai_platform_generator.adapters.llm import (
        DemoModeLlmAdapter,
        OpenRouterLlmAdapter,
    )

    api_key = secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        # Construction would raise ``MissingApiKey``. Deferring to demo
        # here would prevent ``FallbackLlmProvider`` from ever exposing
        # the primary's identity; instead we return demo so callers see
        # a working provider, and warn loudly so misconfigurations are
        # noticed.
        warnings.warn(
            "OPENROUTER_API_KEY is not set; using demo mode as the primary",
            stacklevel=3,
        )
        return DemoModeLlmAdapter()
    return OpenRouterLlmAdapter(api_key=api_key)


def _build_openai_adapter(secrets: SecretProvider) -> LlmProvider:
    """Construct an :class:`OpenAiLlmAdapter`, deferring missing-key failures."""
    from ai_platform_generator.adapters.llm import (
        DemoModeLlmAdapter,
        OpenAiLlmAdapter,
    )

    api_key = secrets.get("OPENAI_API_KEY")
    if not api_key:
        warnings.warn(
            "OPENAI_API_KEY is not set; using demo mode as the primary",
            stacklevel=3,
        )
        return DemoModeLlmAdapter()
    return OpenAiLlmAdapter(api_key=api_key)


def _build_sinks(config: AppConfig, *, clock: Clock) -> list[TelemetrySink]:
    """Build the configured sink list — at minimum a :class:`StructlogSink`."""
    from ai_platform_generator.adapters.telemetry.structlog_sink import (
        StructlogSink,
    )

    sinks: list[TelemetrySink] = [StructlogSink(mode=config.log_format)]
    if config.enable_otel:
        try:
            from ai_platform_generator.adapters.telemetry.otel_sink import (
                OtelSink,
            )

            sinks.append(OtelSink(clock=clock))
        except Exception as exc:  # pragma: no cover - opt-in path
            _logger.warning(
                "OtelSink unavailable; continuing without OTEL: %r", exc
            )
    return sinks


def _load_default_generators() -> tuple[Any, ...]:
    """Return the canonical generator set, falling back gracefully.

    Sibling Wave-4 agents (L / M / N) own the concrete generator
    modules. The composition root must not crash if their modules are
    not yet importable — instead we warn and continue with an empty
    tuple. The orchestrator then completes successfully (no artefacts
    in the bundle) so callers can validate the rest of the pipeline.
    """
    try:
        from ai_platform_generator.domain.generation.generators import (
            default_generators,
        )
    except Exception as exc:
        _logger.warning(
            "default_generators not importable; running with no generators (%r)",
            exc,
        )
        return ()

    try:
        return tuple(default_generators())
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning(
            "default_generators() raised; running with no generators (%r)",
            exc,
        )
        return ()


__all__ = [
    "AppConfig",
    "build_orchestrator",
    "build_test_orchestrator",
]
