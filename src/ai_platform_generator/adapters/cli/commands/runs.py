"""``runs`` Click sub-group — inspect generation-run history.

Two sub-commands per ``05-user-interaction.md`` §4:

* ``list`` — prints every record in
  :class:`JsonlRunRepository`'s file in chronological order.
* ``show <run_id>`` — prints the projection of a single run.

Output is rendered through Q's renderer when available; otherwise a
plain ``click.echo`` listing is used.
"""

from __future__ import annotations

import contextlib
import json
import sys
from typing import Any

import click

from ..exit_codes import EXIT_GENERIC, EXIT_OK, code_for


@click.group("runs")
def runs() -> None:
    """Inspect generation-run history."""


@runs.command("list")
@click.pass_context
def runs_list(ctx: click.Context) -> None:
    """List all recorded generation runs (chronological order)."""
    renderer = ctx.obj["renderer"]
    repo = _build_repo()

    try:
        records = _read_records(repo)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    forwarded = _try_render(renderer, "render_runs_list", records)
    if not forwarded:
        if not records:
            click.echo("(no runs recorded)")
        for r in records:
            click.echo(
                f"  {r.get('run_id', '?'):<36s}  {r.get('started_at', '?'):<25s}  "
                f"{r.get('state', '?')}"
            )
    sys.exit(EXIT_OK)


@runs.command("show")
@click.argument("run_id")
@click.pass_context
def runs_show(ctx: click.Context, run_id: str) -> None:
    """Show the projection for a single run."""
    renderer = ctx.obj["renderer"]
    repo = _build_repo()

    try:
        records = _read_records(repo)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    match = next((r for r in records if r.get("run_id") == run_id), None)
    if match is None:
        click.echo(f"no run with run_id {run_id!r}", err=True)
        sys.exit(EXIT_GENERIC)

    forwarded = _try_render(renderer, "render_run_detail", match)
    if not forwarded:
        click.echo(json.dumps(match, indent=2, sort_keys=True))
    sys.exit(EXIT_OK)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_repo() -> Any:
    """Construct the canonical :class:`JsonlRunRepository`."""
    from ai_platform_generator.adapters.run_repository.jsonl import (
        JsonlRunRepository,
    )

    return JsonlRunRepository()


def _read_records(repo: Any) -> list[dict[str, Any]]:
    """Pull projection records from ``repo``.

    The repository exposes ``_iter_records`` for diagnostic introspection;
    that method is fine to use here because the CLI is in the same
    package and the call is a *read* of an audit log. Falls back to
    ``latest()`` if the private method is not present.
    """
    iter_fn = getattr(repo, "_iter_records", None)
    if callable(iter_fn):
        return list(iter_fn())
    latest = getattr(repo, "latest", None)
    if callable(latest):
        out = []
        record = latest()
        if record is not None:
            out.append(_run_to_dict_safe(record))
        return out
    return []


def _run_to_dict_safe(run: Any) -> dict[str, Any]:
    """Best-effort projection from a :class:`GenerationRun`."""
    return {
        "run_id": getattr(getattr(run, "id", None), "value", str(run)),
        "started_at": str(getattr(run, "started_at", "")),
        "state": getattr(getattr(run, "state", None), "value", str(getattr(run, "state", ""))),
    }


def _try_render(renderer: Any, method: str, payload: Any) -> bool:
    fn = getattr(renderer, method, None)
    if fn is None:
        return False
    try:
        fn(payload)
    except Exception:
        return False
    return True


def _report_error(renderer: Any, exc: Exception) -> None:
    if hasattr(renderer, "error"):
        with contextlib.suppress(Exception):
            renderer.error(exc)


__all__ = ["runs"]
