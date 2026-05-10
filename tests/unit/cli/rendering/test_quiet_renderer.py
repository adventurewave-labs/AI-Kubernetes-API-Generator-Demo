"""Unit tests for :class:`QuietRenderer`."""
from __future__ import annotations

from io import StringIO

from ai_platform_generator.adapters.cli.exit_codes import EXIT_CONFIGURATION
from ai_platform_generator.adapters.cli.rendering.quiet_renderer import (
    QuietRenderer,
)
from ai_platform_generator.application.orchestrator import GenerationSummary
from ai_platform_generator.domain.errors import MissingApiKey
from ai_platform_generator.domain.events import RunStarted


def test_begin_event_end_emit_nothing() -> None:
    err_buf = StringIO()
    renderer = QuietRenderer(stderr=err_buf)
    renderer.begin()
    renderer.event(RunStarted.make(run_id=None, payload={}))
    summary = GenerationSummary(
        run_id="11111111-1111-1111-1111-111111111111",
        state="succeeded",
    )
    renderer.end(summary)
    assert err_buf.getvalue() == ""


def test_error_writes_code_to_stderr_and_returns_exit_code() -> None:
    err_buf = StringIO()
    renderer = QuietRenderer(stderr=err_buf)
    err = MissingApiKey("OPENAI_API_KEY is not set")
    code = renderer.error(err)
    assert code == EXIT_CONFIGURATION
    assert err_buf.getvalue().strip() == err.code
    assert err_buf.getvalue().count("\n") == 1
