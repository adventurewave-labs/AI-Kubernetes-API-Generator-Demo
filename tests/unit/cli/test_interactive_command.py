"""Tests for ``main interactive``.

The interactive command loops over an intent prompt; we drive a single
cycle and immediately quit to keep the test deterministic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_platform_generator.adapters.cli.main import main

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner

    from .conftest import _FakeOrchestrator


def test_interactive_runs_one_cycle_then_quits(
    cli_runner: CliRunner, fake_orchestrator: _FakeOrchestrator
) -> None:
    """One intent cycle plus a ``q`` to quit must exit cleanly."""
    user_input = "Create a VectorDB API\nq\n"

    result = cli_runner.invoke(main, ["interactive"], input=user_input)

    assert result.exit_code == 0, result.stderr or result.stdout

    combined = result.stdout + result.stderr
    # The welcome panel + a run-summary marker should both appear.
    assert any(
        token.lower() in combined.lower()
        for token in ("welcome", "interactive", "ai platform")
    ), f"no welcome panel in output: {combined!r}"

    # And the orchestrator should have been invoked at least once for
    # the single intent we supplied.
    assert fake_orchestrator.calls, "orchestrator was never driven"
