"""Snapshot ``--help`` output for every Click command in the CLI.

Help text is part of the public CLI contract
(:adoc:`docs/ddd/bounded-contexts/05-user-interaction.md` §10) — any
unintentional change is a regression worth catching at PR time. We
compare against checked-in fixtures under
``tests/golden/cli/expected/<cmd_name>.help.txt`` and use the
:option:`--update-golden` flag established in
``tests/golden/conftest.py`` to refresh them.

A help snapshot fails (rather than silently passes) the first time it
is run, so the fixture must be created with::

    pytest tests/golden/cli -k help_snapshot --update-golden

Note that ``--update-golden`` marks the test as :func:`xfail` so a
regen run is recognisable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ai_platform_generator.adapters.cli.main import main

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner


_EXPECTED_DIR = Path(__file__).resolve().parent / "expected"


# Each tuple is (cli_args, fixture_filename). The args drive
# ``cli_runner.invoke(main, [...] + ["--help"])``.
_HELP_TARGETS: tuple[tuple[tuple[str, ...], str], ...] = (
    ((), "main.help.txt"),
    (("generate",), "generate.help.txt"),
    (("interactive",), "interactive.help.txt"),
    (("build",), "build.help.txt"),
    (("examples",), "examples.help.txt"),
    (("cluster",), "cluster.help.txt"),
    (("cluster", "ensure"), "cluster_ensure.help.txt"),
    (("cluster", "teardown"), "cluster_teardown.help.txt"),
    (("cluster", "status"), "cluster_status.help.txt"),
    (("validate",), "validate.help.txt"),
    (("runs",), "runs.help.txt"),
    (("runs", "list"), "runs_list.help.txt"),
    (("runs", "show"), "runs_show.help.txt"),
)


def _normalise(text: str) -> str:
    """Drop trailing whitespace + collapse the help text to a stable form.

    Click's ``--help`` output is generally deterministic but width
    detection drifts between TTY-aware terminals and CI pipes. We
    normalise:

    * trailing whitespace per line;
    * an absolute-path prefix for ``Usage:`` lines (the Click executable
      basename varies between local dev (``pytest``) and CI runners).
    """
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        # Collapse the Usage: prefix to a stable form.
        line = re.sub(
            r"^Usage:\s+\S+",
            "Usage: ai-platform-generator",
            line,
        )
        lines.append(line)
    return "\n".join(lines).rstrip("\n") + "\n"


@pytest.mark.golden
@pytest.mark.parametrize(
    ("argv", "fixture"),
    _HELP_TARGETS,
    ids=[fixture for _, fixture in _HELP_TARGETS],
)
def test_help_snapshot(
    cli_runner: CliRunner,
    argv: tuple[str, ...],
    fixture: str,
    update_golden: bool,
) -> None:
    """Compare ``--help`` output against the on-disk fixture."""
    result = cli_runner.invoke(main, [*argv, "--help"])
    if result.exit_code != 0:
        pytest.fail(
            f"help failed for argv={argv!r}: exit={result.exit_code} "
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )

    actual = _normalise(result.stdout)
    fixture_path = _EXPECTED_DIR / fixture

    if update_golden:
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(actual, encoding="utf-8")
        pytest.xfail(
            f"golden refreshed for {fixture} ({len(actual)} bytes)"
        )

    if not fixture_path.exists():
        pytest.fail(
            f"missing golden fixture {fixture_path} — run with "
            "--update-golden to create it"
        )

    expected = fixture_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"{fixture} drift — re-run with --update-golden if intentional.\n"
        f"--- expected ---\n{expected}\n--- actual ---\n{actual}"
    )
