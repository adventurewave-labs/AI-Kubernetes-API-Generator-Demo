"""Shared fixtures for CLI command tests.

Wave-5 ships the Click commands (Agent P) + renderer protocol (Agent Q)
+ end-to-end CLI tests (Agent R, this file's caller). The composition
root is monkey-patched here so CLI tests never need a live LLM, real
filesystem, or Kind cluster.

Three fixtures are exposed:

* :func:`cli_runner` — a fresh :class:`click.testing.CliRunner` per test
  with stderr split out so renderer separation is observable.
* :func:`fake_orchestrator` — a stub orchestrator that walks every
  expected stage and emits the canonical event sequence into the
  renderer / sink combination. Built on top of Wave-1's
  :class:`RecordingSink`.
* :func:`monkeypatch_composition_to_fakes` — autouse fixture that
  rewires :func:`ai_platform_generator.application.composition.build_orchestrator`
  to return :func:`fake_orchestrator` regardless of caller config. CLI
  command modules import the symbol lazily, so the patch reaches
  through ``main`` -> sub-command without further plumbing.
* :func:`golden_dir` — the golden-CLI fixture root.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.domain.events import (
    ArtifactBundleSealed,
    ArtifactGenerated,
    CodegenRequestParsed,
    IntentSubmitted,
    IRConstructed,
    LlmInvocationStarted,
    LlmInvocationSucceeded,
    RunStarted,
    RunSucceeded,
    StageStarted,
    StageSucceeded,
)
from ai_platform_generator.domain.values import RunId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import (
        GenerateParams,
        GenerationSummary,
    )


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a fresh :class:`CliRunner` for one CLI test.

    Click 8.2+ dropped the ``mix_stderr`` keyword and split stderr from
    stdout by default, so we just use the no-arg constructor. Tests that
    grep for substrings concatenate ``result.stdout + result.stderr`` —
    on Click 8.2+ ``result.stderr`` is always present (empty when no
    bytes were written to it).
    """
    return CliRunner()


@pytest.fixture
def golden_dir() -> Path:
    """Root of the CLI golden-fixture tree (``tests/golden/cli``)."""
    return Path(__file__).resolve().parent.parent.parent / "golden" / "cli"


# ---------------------------------------------------------------------------
# Fake orchestrator
# ---------------------------------------------------------------------------


class _FakeOrchestrator:
    """Stub orchestrator that emits the canonical Wave-5 event sequence.

    The CLI tests assert against:

    * an explicit ordered subsequence of event names (per
      ``docs/ddd/05-domain-events.md`` §3);
    * the resulting :class:`GenerationSummary`;
    * an injectable typed error (used by failure-path tests).

    Per the wave-5 contract this stub is wired in via
    :func:`monkeypatch_composition_to_fakes`; tests that need to
    customise behaviour reach in via ``ctx.obj["fake_orchestrator"]``
    or directly via the returned fixture handle.
    """

    def __init__(self) -> None:
        self.sink = RecordingSink()
        self.calls: list[Any] = []
        self.raise_on_run: BaseException | None = None
        self.summary_overrides: dict[str, Any] = {}
        # Number of artefacts the fake should claim to have produced.
        self.artefact_count: int = 3

    # ----- failure injection -------------------------------------------
    def will_raise(self, exc: BaseException) -> None:
        """Cause the next :meth:`run` call to raise ``exc``."""
        self.raise_on_run = exc

    # ----- protocol ----------------------------------------------------
    def run(self, params: GenerateParams) -> GenerationSummary:
        """Walk the canonical stages, emitting an event per phase."""
        self.calls.append(params)

        run_id = RunId.new()

        # 1. RunStarted
        self.sink.emit(
            RunStarted.make(
                run_id=run_id,
                payload={
                    "run_id": run_id.value,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

        if self.raise_on_run is not None:
            exc = self.raise_on_run
            self.raise_on_run = None
            raise exc

        # 2. Intent stage
        self.sink.emit(
            StageStarted.make(run_id=run_id, payload={"stage": "interpret"})
        )
        self.sink.emit(
            IntentSubmitted.make(
                run_id=run_id,
                payload={"text": params.intent_text},
            )
        )
        self.sink.emit(
            LlmInvocationStarted.make(
                run_id=run_id, payload={"provider": "fake"}
            )
        )
        self.sink.emit(
            LlmInvocationSucceeded.make(
                run_id=run_id,
                payload={
                    "provider": "fake",
                    "tokens_in": 10,
                    "tokens_out": 20,
                },
            )
        )
        self.sink.emit(
            CodegenRequestParsed.make(
                run_id=run_id,
                payload={
                    "gvk": {
                        "group": "ai.cnoe.io",
                        "version": "v1alpha1",
                        "kind": "VectorDB",
                    },
                },
            )
        )
        self.sink.emit(
            StageSucceeded.make(run_id=run_id, payload={"stage": "interpret"})
        )

        # 3. Modelling stage
        self.sink.emit(
            StageStarted.make(run_id=run_id, payload={"stage": "model"})
        )
        self.sink.emit(
            IRConstructed.make(
                run_id=run_id,
                payload={"kind": "VectorDB", "property_count": 2},
            )
        )
        self.sink.emit(
            StageSucceeded.make(run_id=run_id, payload={"stage": "model"})
        )

        # 4. Artefact-generation stage
        self.sink.emit(
            StageStarted.make(run_id=run_id, payload={"stage": "generate"})
        )
        for idx in range(self.artefact_count):
            self.sink.emit(
                ArtifactGenerated.make(
                    run_id=run_id,
                    payload={"index": idx, "type": "OPENAPI"},
                )
            )
        self.sink.emit(
            ArtifactBundleSealed.make(
                run_id=run_id,
                payload={"file_count": self.artefact_count},
            )
        )
        self.sink.emit(
            StageSucceeded.make(run_id=run_id, payload={"stage": "generate"})
        )

        # 5. RunSucceeded
        self.sink.emit(
            RunSucceeded.make(
                run_id=run_id,
                payload={"run_id": run_id.value, "duration_ms": 5},
            )
        )

        # Build a minimal-but-shaped summary that won't import the
        # real Pydantic class (avoids hard-coupling to the still-shifting
        # GenerationSummary surface).
        return SimpleNamespace(
            run_id=run_id,
            state="succeeded",
            gvk=SimpleNamespace(
                group="ai.cnoe.io", version="v1alpha1", kind="VectorDB"
            ),
            bundle_dir=Path("generated/vector-db"),
            artefact_paths=[
                Path(f"generated/vector-db/file{i}")
                for i in range(self.artefact_count)
            ],
            cluster_name=None,
            deployment_status=None,
            duration_ms=5,
            provider_mode=None,
            **self.summary_overrides,
        )


@pytest.fixture
def fake_orchestrator() -> _FakeOrchestrator:
    """Return a fresh :class:`_FakeOrchestrator` for one test."""
    return _FakeOrchestrator()


# ---------------------------------------------------------------------------
# Composition-root patch
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def monkeypatch_composition_to_fakes(
    monkeypatch: pytest.MonkeyPatch,
    fake_orchestrator: _FakeOrchestrator,
) -> Iterator[_FakeOrchestrator]:
    """Patch ``build_orchestrator`` to return the fake.

    The CLI commands import the symbol from
    :mod:`ai_platform_generator.application.composition`. We patch on
    that module so any caller that does
    ``from ai_platform_generator.application.composition import build_orchestrator``
    *or* ``import ai_platform_generator.application.composition as c;
    c.build_orchestrator(...)`` sees the fake.
    """
    from ai_platform_generator.application import composition as _composition

    def _build(*_args: Any, **_kwargs: Any) -> _FakeOrchestrator:
        return fake_orchestrator

    monkeypatch.setattr(_composition, "build_orchestrator", _build)
    monkeypatch.setattr(_composition, "build_test_orchestrator", _build)
    yield fake_orchestrator
