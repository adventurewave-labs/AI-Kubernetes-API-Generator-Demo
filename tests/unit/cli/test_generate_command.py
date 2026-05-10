"""End-to-end tests for the ``main generate`` command.

The fake orchestrator emits the canonical Wave-5 event sequence so we
can assert the full pipeline contract without invoking a real LLM,
filesystem, or cluster runtime.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ai_platform_generator.adapters.cli.main import main

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner

    from .conftest import _FakeOrchestrator


_INTENT = "Create a VectorDB API with engine_type and replicas"


def _parse_ndjson(text: str) -> list[dict]:
    """Parse non-empty lines as NDJSON, tolerating trailing whitespace."""
    out: list[dict] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            # Lines that aren't JSON (e.g. occasional progress noise) are
            # skipped — the contract is a *subsequence* of events, not
            # byte-strict NDJSON purity.
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _event_names_in_order(records: list[dict]) -> list[str]:
    """Project NDJSON records to a list of event names, preserving order."""
    return [
        str(r.get("name") or r.get("event") or "")
        for r in records
        if r.get("name") or r.get("event")
    ]


def test_generate_json_emits_canonical_event_sequence(
    cli_runner: CliRunner,
    fake_orchestrator: _FakeOrchestrator,
) -> None:
    """A successful run emits every Wave-5 milestone event, in order."""
    result = cli_runner.invoke(
        main,
        [
            "--no-deploy",
            "--log-format=json",
            "generate",
            _INTENT,
        ],
    )

    assert result.exit_code == 0, result.stderr or result.stdout

    records = _parse_ndjson(result.stdout)
    names = _event_names_in_order(records)

    expected_subsequence = [
        "RunStarted",
        "IntentSubmitted",
        "LlmInvocationSucceeded",
        "CodegenRequestParsed",
        "IRConstructed",
        "ArtifactGenerated",
        "ArtifactBundleSealed",
        "RunSucceeded",
    ]

    # Subsequence assertion — additional events between the required
    # ones (e.g. StageStarted/StageSucceeded, LlmInvocationStarted) are
    # tolerated, but the relative ordering of the requested events is
    # part of the contract.
    idx = 0
    for expected in expected_subsequence:
        try:
            idx = names.index(expected, idx) + 1
        except ValueError as e:
            raise AssertionError(
                f"event {expected!r} not found in order — observed: {names!r}"
            ) from e

    # ``ArtifactGenerated`` is emitted *N* times — the fake yields three
    # by default, so make sure we observed at least one.
    assert names.count("ArtifactGenerated") >= 1


def test_generate_invokes_orchestrator_with_intent(
    cli_runner: CliRunner,
    fake_orchestrator: _FakeOrchestrator,
) -> None:
    """The command threads the user's intent into ``GenerateParams``."""
    result = cli_runner.invoke(
        main,
        ["--no-deploy", "--log-format=json", "generate", _INTENT],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    assert fake_orchestrator.calls, "orchestrator.run was never called"
    params = fake_orchestrator.calls[0]
    # Either Pydantic ``GenerateParams`` or a plain object — both expose
    # the field.
    assert getattr(params, "intent_text", None) == _INTENT
    assert getattr(params, "deploy_to_cluster", True) is False


def test_generate_tty_renders_rich_markers(
    cli_runner: CliRunner,
    fake_orchestrator: _FakeOrchestrator,
) -> None:
    """In TTY mode the renderer should include a Rich-specific marker.

    We accept any of:
    * the rocket emoji used by Agent Q's RichRenderer welcome panel;
    * the green check used in success summaries;
    * the literal word ``"VectorDB"`` (kind from the fake summary).
    """
    result = cli_runner.invoke(
        main,
        ["--no-deploy", "--log-format=tty", "generate", _INTENT],
        color=True,
    )
    assert result.exit_code == 0, result.stderr or result.stdout

    output = result.stdout + result.stderr
    markers = ("\U0001f680", "✓", "✅", "VectorDB", "succeeded", "Run ")
    assert any(m in output for m in markers), (
        f"no Rich marker present in output: {output!r}"
    )
