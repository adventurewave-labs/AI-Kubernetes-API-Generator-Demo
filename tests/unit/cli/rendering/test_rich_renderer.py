"""Unit tests for :class:`RichRenderer`.

We feed a synthetic event sequence into the renderer (with a Rich console
configured to write into a ``StringIO``) and assert that all the salient
strings (stage labels, artefact paths, demo-mode banner, error code +
remediation hint) end up in the captured output.
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from ai_platform_generator.adapters.cli.exit_codes import (
    EXIT_INTENT,
    EXIT_PERSISTENCE,
)
from ai_platform_generator.adapters.cli.rendering.rich_renderer import (
    RichRenderer,
)
from ai_platform_generator.application.orchestrator import GenerationSummary
from ai_platform_generator.domain.errors import (
    LlmUnavailable,
    PersistenceError,
)
from ai_platform_generator.domain.events import (
    ArtifactBundleSealed,
    ArtifactGenerated,
    DemoModeEngaged,
    LlmInvocationSucceeded,
    RunStarted,
    RunSucceeded,
    StageStarted,
    StageSucceeded,
)


def _make_renderer() -> tuple[RichRenderer, StringIO]:
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=False,
        width=120,
        no_color=True,
        record=False,
    )
    return RichRenderer(console=console), buffer


def test_begin_prints_welcome_banner() -> None:
    renderer, buffer = _make_renderer()
    renderer.begin()
    output = buffer.getvalue()
    assert "AI Kubernetes API Generator" in output
    assert "Natural language" in output


def test_event_sequence_renders_stages_and_artefacts() -> None:
    renderer, buffer = _make_renderer()
    renderer.begin()

    renderer.event(RunStarted.make(run_id=None, payload={}))
    for stage in ("interpret", "model", "generate"):
        renderer.event(StageStarted.make(run_id=None, payload={"stage": stage}))
        renderer.event(
            StageSucceeded.make(
                run_id=None, payload={"stage": stage, "elapsed_ms": 12}
            )
        )

    renderer.event(
        ArtifactGenerated.make(
            run_id=None,
            payload={"artifact_type": "crd", "path": "/tmp/out/widget-crd.yaml"},
        )
    )
    renderer.event(
        ArtifactGenerated.make(
            run_id=None,
            payload={"artifact_type": "instance", "path": "/tmp/out/widget.yaml"},
        )
    )
    renderer.event(
        ArtifactBundleSealed.make(
            run_id=None, payload={"target_dir": "/tmp/out"}
        )
    )

    summary = GenerationSummary(
        run_id="11111111-1111-1111-1111-111111111111",
        state="succeeded",
        gvk="example.io/v1/Widget",
        bundle_dir=Path("/tmp/out"),
        artefact_paths=[Path("/tmp/out/widget-crd.yaml")],
        cluster_name=None,
        deployment_status=None,
        duration_ms=345,
        provider_mode="live",
    )
    renderer.event(RunSucceeded.make(run_id=None, payload={}))
    renderer.end(summary)

    output = buffer.getvalue()
    # Stage labels
    for label in ("Interpret", "Model", "Generate"):
        assert label in output
    # Artefacts
    assert "generated" in output
    assert "/tmp/out/widget-crd.yaml" in output
    # Bundle sealed
    assert "bundle sealed at" in output
    assert "/tmp/out" in output
    # Summary panel
    assert "GVK" in output
    assert "Widget" in output
    assert "345 ms" in output


def test_llm_invocation_dim_token_line() -> None:
    renderer, buffer = _make_renderer()
    renderer.begin()
    renderer.event(RunStarted.make(run_id=None, payload={}))
    renderer.event(
        LlmInvocationSucceeded.make(
            run_id=None,
            payload={"prompt_tokens": 128, "completion_tokens": 256},
        )
    )
    output = buffer.getvalue()
    assert "tokens: 128+256" in output


def test_demo_mode_engaged_shows_yellow_banner() -> None:
    renderer, buffer = _make_renderer()
    renderer.event(
        DemoModeEngaged.make(
            run_id=None, payload={"reason": "E_INTENT_LLM_UNAVAILABLE"}
        )
    )
    output = buffer.getvalue()
    assert "demo mode" in output
    assert "E_INTENT_LLM_UNAVAILABLE" in output


def test_unknown_event_is_silent_without_debug() -> None:
    renderer, buffer = _make_renderer()
    # An event we do not handle in the switch.
    from ai_platform_generator.domain.events import IntentSubmitted

    renderer.event(IntentSubmitted.make(run_id=None, payload={"text": "hi"}))
    assert buffer.getvalue() == ""


def test_error_renders_panel_and_returns_exit_code() -> None:
    renderer, buffer = _make_renderer()
    # The base ``PlatformGeneratorError.__init__`` collects arbitrary kwargs
    # into ``extra``; the renderer reads ``remediation_hint`` from there.
    err = LlmUnavailable(
        "LLM provider is offline",
        remediation_hint="Re-run with --demo to use the curated scenario",
    )

    code = renderer.error(err)
    output = buffer.getvalue()

    assert code == EXIT_INTENT
    assert err.code in output
    assert "LLM provider is offline" in output
    assert "Remediation:" in output
    assert "Re-run with --demo" in output


def test_error_remediation_falls_back_to_none_marker() -> None:
    renderer, buffer = _make_renderer()
    err = PersistenceError("Disk full")
    code = renderer.error(err)
    assert code == EXIT_PERSISTENCE
    assert "(none)" in buffer.getvalue()


@pytest.mark.parametrize("env_var", ["NO_COLOR", "CLICOLOR"])
def test_default_console_honours_no_color(monkeypatch: pytest.MonkeyPatch, env_var: str) -> None:
    if env_var == "NO_COLOR":
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.setenv("CLICOLOR", "0")
    renderer = RichRenderer()
    assert renderer.console.no_color is True
