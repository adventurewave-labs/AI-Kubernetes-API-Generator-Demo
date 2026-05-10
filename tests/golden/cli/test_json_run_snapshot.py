"""Snapshot the NDJSON event stream for a single ``generate`` run.

Captures stdout from::

    main --no-deploy --log-format=json generate "Create a VectorDB API …"

Sanitises non-deterministic fields (timestamps, run-ids, event-ids,
durations) to fixed placeholders, then compares against
``tests/golden/cli/expected/vector_db_run.ndjson``. Honours the same
``--update-golden`` mechanism as the help snapshots.

Implementation note
-------------------
The CLI tests' :mod:`tests.unit.cli.conftest` fixtures *autouse* the
fake-orchestrator wiring. We import them directly here so this golden
test gets the same deterministic substrate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Re-use the unit-test conftest fixtures (cli_runner, fake_orchestrator,
# monkeypatch_composition_to_fakes) so the fake orchestrator drives the
# event stream deterministically.
pytest_plugins = ("tests.unit.cli.conftest",)

from ai_platform_generator.adapters.cli.main import main  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner


_EXPECTED = (
    Path(__file__).resolve().parent / "expected" / "vector_db_run.ndjson"
)
_INTENT = "Create a VectorDB API with engine_type and replicas"

# Substitution rules — run before the comparison so non-deterministic
# fields collapse to a stable placeholder. Order matters: longer keys
# first to avoid a partial replacement clobbering a more-specific one.
_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # ISO-8601 timestamps with timezone.
    (
        re.compile(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})"
        ),
        "<TIMESTAMP>",
    ),
    # UUIDv4 (event_id, causation_id).
    (
        re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        ),
        "<UUID>",
    ),
    # RunId values — ULIDs / hex / `run-…` prefixes alike. Only match
    # tokens that contain at least one digit so we don't collapse
    # long CamelCase event names (e.g. ``LlmInvocationSucceeded``).
    (
        re.compile(r"\brun-[0-9A-Za-z]{4,}\b"),
        "<RUN_ID>",
    ),
    (
        re.compile(r"\b(?=[0-9A-Za-z]{20,}\b)(?=[^\"]*[0-9])[0-9A-Za-z]{20,}\b"),
        "<RUN_ID>",
    ),
    # duration_ms — small integers vary per run.
    (
        re.compile(r'"duration_ms"\s*:\s*\d+'),
        '"duration_ms": <DURATION_MS>',
    ),
)


def _sanitise_line(line: str) -> str:
    out = line
    for pattern, replacement in _SUBSTITUTIONS:
        out = pattern.sub(replacement, out)
    return out


def _sanitise_ndjson(text: str) -> str:
    """Drop blank lines, parse + re-serialise each JSON object, then sub."""
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Skip non-JSON lines (e.g. accidental Rich output) so we
            # snapshot the *event stream*, not the renderer's whole
            # stdout.
            continue
        normalised = json.dumps(obj, sort_keys=True, separators=(", ", ": "))
        cleaned.append(_sanitise_line(normalised))
    return "\n".join(cleaned) + "\n" if cleaned else ""


@pytest.mark.golden
def test_vector_db_run_event_stream(
    cli_runner: CliRunner,
    update_golden: bool,
) -> None:
    """Snapshot the canonical VectorDB run's NDJSON event stream."""
    result = cli_runner.invoke(
        main,
        ["--no-deploy", "--log-format=json", "generate", _INTENT],
    )
    if result.exit_code != 0:
        pytest.fail(
            "generate command failed: "
            f"exit={result.exit_code} stderr={result.stderr!r} "
            f"stdout={result.stdout!r}"
        )

    actual = _sanitise_ndjson(result.stdout)

    if update_golden:
        _EXPECTED.parent.mkdir(parents=True, exist_ok=True)
        _EXPECTED.write_text(actual, encoding="utf-8")
        pytest.xfail(
            f"golden refreshed for {_EXPECTED.name} ({len(actual)} bytes)"
        )

    if not _EXPECTED.exists():
        pytest.fail(
            f"missing golden fixture {_EXPECTED} — run with "
            "--update-golden to create it"
        )

    expected = _EXPECTED.read_text(encoding="utf-8")
    assert actual == expected, (
        f"vector_db_run.ndjson drift — re-run with --update-golden if "
        f"intentional.\n--- expected ---\n{expected}\n--- actual ---\n{actual}"
    )
