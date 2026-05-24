"""``interactive`` Click command — REPL-style chained generation.

Realises ``docs/ddd/bounded-contexts/05-user-interaction.md`` §6.

The command captures the global options at session start (model,
output dir, deploy flag, …) and then loops:

1. Welcome panel (delegated to the renderer).
2. Prompt for an intent. If the user terminates a line with ``\\`` we
   keep reading until a blank line — primitive multiline support.
3. Run a single :class:`GenerateParams` through the same orchestrator
   as the one-shot ``generate`` command.
4. Render the summary.
5. Offer next-step actions: ``[d]eploy this``, ``[r]egenerate``,
   ``[e]dit intent``, ``[n]ew``, ``[q]uit``.

Configuration captured at session start applies to subsequent runs
unless the user explicitly toggles them via menu actions.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import click

from ..exit_codes import EXIT_INTERRUPTED, EXIT_OK, code_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


_PROMPT_HEADER = "describe the API you want (end with empty line; \\ for multiline):"
_MENU_PROMPT = "next: [d]eploy this | [r]egenerate | [e]dit | [n]ew | [q]uit"


@click.command()
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Interactive REPL — chain multiple generations with shared config."""
    opts: dict[str, Any] = ctx.obj["opts"]
    renderer = ctx.obj["renderer"]

    if hasattr(renderer, "begin"):
        with contextlib.suppress(Exception):
            renderer.begin()

    click.echo("AI Kubernetes API Generator — interactive mode")
    click.echo("Type 'quit' on the first line to leave.")

    last_intent: str | None = None
    last_summary: Any = None

    try:
        while True:
            intent = _prompt_for_intent(_PROMPT_HEADER)
            if intent is None or intent.strip().lower() in {"quit", "exit", ":q"}:
                break

            last_intent = intent
            last_summary = _run_one(opts, renderer, intent)

            action = _prompt_menu(last_summary)
            if action == "q":
                break
            if action == "r" and last_intent is not None:
                last_summary = _run_one(opts, renderer, last_intent)
                continue
            if action == "e" and last_intent is not None:
                edited = _prompt_for_intent(
                    "edit intent (existing text below; resubmit to run):"
                )
                if edited:
                    last_intent = edited
                    last_summary = _run_one(opts, renderer, edited)
                continue
            if action == "d":
                # Re-run with deploy forced on.
                forced_opts = dict(opts)
                forced_opts["deploy"] = True
                last_summary = _run_one(
                    forced_opts, renderer, last_intent or "", reuse_orchestrator=True
                )
                continue
            # 'n' or anything else: fall through to the next prompt.
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERRUPTED)

    sys.exit(EXIT_OK)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prompt_for_intent(header: str) -> str | None:
    """Read a (possibly multi-line) intent string from stdin.

    A line ending in ``\\`` continues onto the next line; an empty
    line terminates input. Returns ``None`` on EOF.
    """
    click.echo(header)
    lines: list[str] = []
    try:
        while True:
            line = click.prompt("> ", default="", show_default=False)
            if line == "" and not lines:
                return None
            if line.endswith("\\"):
                lines.append(line[:-1])
                continue
            if line == "" and lines:
                break
            lines.append(line)
            break
    except (EOFError, click.Abort):
        return None
    text = "\n".join(lines).strip()
    return text or None


def _prompt_menu(_summary: Any) -> str:
    """Prompt the user for the next action; returns a single char."""
    click.echo(_MENU_PROMPT)
    try:
        choice = click.prompt(
            "?", type=click.Choice(["d", "r", "e", "n", "q"]), default="n"
        )
    except (EOFError, click.Abort):
        return "q"
    return str(choice).lower()


def _run_one(
    opts: dict[str, Any],
    renderer: Any,
    intent: str,
    *,
    reuse_orchestrator: bool = False,
) -> Any:
    """Drive a single Generation Run; mirrors ``generate.generate``."""
    # Lazy imports keep the interactive module cheap to import.
    from ai_platform_generator.application.composition import (
        AppConfig,
        build_orchestrator,
    )
    from ai_platform_generator.application.orchestrator import GenerateParams

    config_kwargs: dict[str, Any] = {
        "llm_provider": opts.get("llm_provider", "openrouter"),
        "allow_demo_mode": opts.get("allow_demo_mode", True),
        "cluster_name": opts.get("cluster_name", "ai-platform-demo"),
        "log_format": _resolve_log_format(opts),
        "enable_otel": bool(opts.get("otel", False)),
    }
    if opts.get("output_dir"):
        out_path = Path(str(opts["output_dir"])).resolve()
        config_kwargs["output_dir"] = out_path
        # Anchor the filesystem repo's traversal-safety root at the
        # user-supplied output directory so writes under it are allowed.
        config_kwargs["artifact_root"] = out_path
    config = AppConfig(**config_kwargs)
    orchestrator = build_orchestrator(config)
    params = GenerateParams(
        intent_text=intent,
        output_dir=opts.get("output_dir"),
        deploy_to_cluster=bool(opts.get("deploy", True)),
        cluster_name=opts.get("cluster_name", "ai-platform-demo"),
        allow_demo_mode=bool(opts.get("allow_demo_mode", True)),
        log_format=_resolve_log_format(opts),
    )

    _ = reuse_orchestrator  # reserved for a future optimisation

    try:
        summary = orchestrator.run(params)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if hasattr(renderer, "error"):
            with contextlib.suppress(Exception):
                renderer.error(exc)
        else:  # pragma: no cover - defensive
            click.echo(f"error: {exc}", err=True)
        # Translate to an exit code but stay in the loop — the user can
        # quit explicitly. We keep the code in scope for diagnostics.
        _ = code_for(exc)
        return None

    if hasattr(renderer, "end"):
        with contextlib.suppress(Exception):
            renderer.end(summary)
    return summary


def _resolve_log_format(opts: dict[str, Any]) -> Literal["tty", "json", "quiet"]:
    explicit = opts.get("log_format")
    if explicit in ("tty", "json", "quiet"):
        return cast('Literal["tty", "json", "quiet"]', explicit)
    if not sys.stdout.isatty():
        return "json"
    return "tty"


__all__ = ["interactive"]
