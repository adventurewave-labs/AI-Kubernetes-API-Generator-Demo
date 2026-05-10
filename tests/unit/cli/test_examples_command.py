"""Tests for ``main examples`` and ``main examples --scenario <name>``.

The eight curated demo scenarios live in
:class:`ai_platform_generator.adapters.llm.demo_catalog.DemoCatalog`;
the ``examples`` command surfaces them so users can pick one without
crafting a free-text intent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ai_platform_generator.adapters.cli.main import main
from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner


_CATALOGUE = DemoCatalog()
_SCENARIO_NAMES = tuple(s.name for s in _CATALOGUE.scenarios)


def test_examples_lists_all_eight_scenarios(cli_runner: CliRunner) -> None:
    """``main examples`` lists every catalogued scenario by name."""
    result = cli_runner.invoke(main, ["examples"])

    assert result.exit_code == 0, result.stderr or result.stdout

    combined = result.stdout + result.stderr
    # All eight built-in scenarios must appear in the output.
    assert len(_SCENARIO_NAMES) == 8, (
        f"DemoCatalog ships {len(_SCENARIO_NAMES)} scenarios, expected 8"
    )
    for name in _SCENARIO_NAMES:
        assert name in combined, (
            f"scenario {name!r} missing from `examples` output: {combined!r}"
        )


@pytest.mark.parametrize(
    ("scenario_name", "expected_kind"),
    [
        ("postgres-cluster", "PostgresCluster"),
        ("vector-db", "VectorDB"),
        ("notebook", "Notebook"),
    ],
)
def test_examples_scenario_shows_gvk(
    cli_runner: CliRunner,
    scenario_name: str,
    expected_kind: str,
) -> None:
    """``main examples --scenario X`` surfaces that scenario's GVK kind."""
    result = cli_runner.invoke(
        main, ["examples", "--scenario", scenario_name]
    )

    assert result.exit_code == 0, result.stderr or result.stdout

    combined = result.stdout + result.stderr
    assert expected_kind in combined, (
        f"GVK kind {expected_kind!r} missing for scenario {scenario_name!r}: "
        f"{combined!r}"
    )
