"""``examples`` Click command — list / show demo scenarios.

Reads :class:`DemoCatalog` from
:mod:`ai_platform_generator.adapters.llm.demo_catalog` (Wave 3) and
defers all rendering to the renderer captured by ``main``. When the
renderer cannot show a structured object (Agent Q's package not yet
landed or in fallback mode) we fall back to a tiny ``click.echo``-
based listing so the command is operational on its own.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click

from ..exit_codes import EXIT_GENERIC, code_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.adapters.llm.demo_catalog import (
        DemoCatalog,
        DemoScenario,
    )


def _scenario_choices() -> list[str]:
    """Return the catalogue's scenario names for ``click.Choice``."""
    try:
        from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
    except ImportError:  # pragma: no cover - the package is in-tree
        return []
    return [s.name for s in DemoCatalog().scenarios]


@click.command()
@click.option(
    "--scenario",
    type=click.Choice(_scenario_choices() or ["postgres-cluster"]),
    default=None,
    help="Show details of a single scenario instead of the full list.",
)
@click.pass_context
def examples(ctx: click.Context, scenario: str | None) -> None:
    """List or show details of the demo scenarios."""
    renderer = ctx.obj["renderer"]

    try:
        from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog

        catalog: DemoCatalog = DemoCatalog()
    except Exception as exc:  # pragma: no cover - defensive
        if hasattr(renderer, "error"):
            renderer.error(exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    if scenario is None:
        _render_list(renderer, catalog)
    else:
        try:
            chosen = catalog.by_name(scenario)
        except KeyError:
            click.echo(f"unknown scenario: {scenario}", err=True)
            sys.exit(EXIT_GENERIC)
        _render_one(renderer, chosen)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_list(renderer: Any, catalog: DemoCatalog) -> None:
    """Forward to the renderer; fall back to plain text."""
    forwarded = _try_render(renderer, "render_examples", catalog)
    if forwarded:
        return
    for s in catalog.scenarios:
        kind = s.request.get("gvk", {}).get("kind", "?")
        keywords = ", ".join(s.keywords)
        click.echo(f"  {s.name:<20s} {kind:<24s} keywords: {keywords}")


def _render_one(renderer: Any, scenario: DemoScenario) -> None:
    """Forward to the renderer; fall back to plain text."""
    forwarded = _try_render(renderer, "render_example", scenario)
    if forwarded:
        return
    click.echo(f"name: {scenario.name}")
    click.echo(f"keywords: {', '.join(scenario.keywords)}")
    gvk = scenario.request.get("gvk", {})
    click.echo(
        f"gvk: {gvk.get('group', '?')}/{gvk.get('version', '?')}/{gvk.get('kind', '?')}"
    )
    click.echo(f"description: {scenario.request.get('description', '')}")


def _try_render(renderer: Any, method: str, payload: Any) -> bool:
    """Call ``renderer.<method>(payload)`` if it exists; swallow errors."""
    fn = getattr(renderer, method, None)
    if fn is None:
        return False
    try:
        fn(payload)
    except Exception:
        return False
    return True


__all__ = ["examples"]
