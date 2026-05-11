"""``generate`` Click command.

Maps to the ``GenerateFromIntent`` use case
(``docs/ddd/bounded-contexts/05-user-interaction.md`` §4).

The command builds an :class:`AppConfig` from the global options on
``ctx.obj["opts"]``, asks the composition root for an orchestrator,
then drives a single Generation Run with a :class:`GenerateParams`
shaped from the same options. The renderer captured by the ``main``
group is bridged onto the orchestrator's :class:`TelemetrySink` so
``begin`` / ``event`` / ``end`` / ``error`` fire as the run progresses.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Literal, cast

import click

from ..exit_codes import EXIT_GENERIC, EXIT_INTERRUPTED, code_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.composition import AppConfig
    from ai_platform_generator.application.orchestrator import (
        GenerateParams,
        GenerationOrchestrator,
    )


@click.command()
@click.argument("description")
@click.option(
    "--output-format",
    type=click.Choice(["json", "yaml", "summary"]),
    default="summary",
    show_default=True,
    help="How the post-run summary should be rendered.",
)
@click.pass_context
def generate(ctx: click.Context, description: str, output_format: str) -> None:
    """Generate a Kubernetes API from a natural-language description."""
    opts: dict[str, Any] = ctx.obj["opts"]
    renderer = ctx.obj["renderer"]

    config = _build_app_config(opts)
    orchestrator = _build_orchestrator(config)

    params = _build_generate_params(description, opts)

    _subscribe_renderer(orchestrator, renderer)

    try:
        renderer.begin()
        summary = orchestrator.run(params)
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERRUPTED)
    except Exception as exc:
        # Typed errors get a stable exit code; everything else gets
        # the generic-error code. Renderer.error returns the code so
        # tests can stub it.
        code = renderer.error(exc) if hasattr(renderer, "error") else code_for(exc)
        sys.exit(code if code is not None else EXIT_GENERIC)

    # Forward the summary to the renderer; tolerate output_format being
    # advisory only — the renderer itself decides the wire shape.
    if hasattr(renderer, "end"):
        renderer.end(summary)
    if output_format == "json":
        _emit_json_summary(summary)
    elif output_format == "yaml":
        _emit_yaml_summary(summary)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app_config(opts: dict[str, Any]) -> AppConfig:
    """Translate the global Click options into an :class:`AppConfig`."""
    from ai_platform_generator.application.composition import AppConfig

    kwargs: dict[str, Any] = {
        "llm_provider": opts.get("llm_provider", "openrouter"),
        "allow_demo_mode": opts.get("allow_demo_mode", True),
        "cluster_name": opts.get("cluster_name", "ai-platform-demo"),
        "log_format": _resolve_log_format(opts),
        "enable_otel": bool(opts.get("otel", False)),
    }
    out_dir = opts.get("output_dir")
    if out_dir is not None:
        kwargs["output_dir"] = out_dir
    return AppConfig(**kwargs)


def _build_orchestrator(config: AppConfig) -> GenerationOrchestrator:
    """Materialise the orchestrator from the composition root."""
    from ai_platform_generator.application.composition import build_orchestrator

    return build_orchestrator(config)


def _build_generate_params(description: str, opts: dict[str, Any]) -> GenerateParams:
    """Build the :class:`GenerateParams` for a single CLI invocation."""
    from ai_platform_generator.application.orchestrator import GenerateParams

    return GenerateParams(
        intent_text=description,
        output_dir=opts.get("output_dir"),
        deploy_to_cluster=bool(opts.get("deploy", True)),
        cluster_name=opts.get("cluster_name", "ai-platform-demo"),
        allow_demo_mode=bool(opts.get("allow_demo_mode", True)),
        log_format=_resolve_log_format(opts),
    )


def _resolve_log_format(opts: dict[str, Any]) -> Literal["tty", "json", "quiet"]:
    """Mirror :func:`adapters.cli.main._resolve_log_format` without import cycles."""
    explicit = opts.get("log_format")
    if explicit in ("tty", "json", "quiet"):
        return cast('Literal["tty", "json", "quiet"]', explicit)
    if not sys.stdout.isatty():
        return "json"
    return "tty"


def _subscribe_renderer(orchestrator: GenerationOrchestrator, renderer: Any) -> None:
    """Bridge the renderer onto the orchestrator's telemetry sink.

    The orchestrator publishes :class:`DomainEvent`s through its
    ``_events`` :class:`TelemetrySink`. We wrap that sink in an adapter
    that *also* forwards each event to ``renderer.event`` so progress
    panels / JSON lines fire as the saga advances.

    Test doubles expose their sink as ``sink`` (rather than ``_events``);
    we honour either.
    """
    import contextlib

    sink = getattr(orchestrator, "_events", None)
    if sink is None or not hasattr(sink, "emit"):
        sink = getattr(orchestrator, "sink", None)
    if sink is None or not hasattr(sink, "emit"):
        return

    original_emit = sink.emit

    def _tee_emit(event: Any) -> None:
        try:
            original_emit(event)
        finally:
            if hasattr(renderer, "event"):
                # Never let a rendering failure stop the run.
                with contextlib.suppress(Exception):
                    renderer.event(event)

    sink.emit = _tee_emit


def _emit_json_summary(summary: Any) -> None:
    """Serialise ``summary`` as JSON to stdout (best-effort)."""
    import json

    payload = _summary_to_dict(summary)
    click.echo(json.dumps(payload, default=str, sort_keys=True))


def _emit_yaml_summary(summary: Any) -> None:
    """Serialise ``summary`` as YAML to stdout (best-effort)."""
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml is a hard dependency
        _emit_json_summary(summary)
        return

    payload = _summary_to_dict(summary)
    click.echo(yaml.safe_dump(payload, sort_keys=True).rstrip())


def _summary_to_dict(summary: Any) -> dict[str, Any]:
    """Best-effort mapping of a :class:`GenerationSummary` to a plain dict."""
    if hasattr(summary, "model_dump"):
        return dict(summary.model_dump(mode="json"))
    return {
        "run_id": str(getattr(summary, "run_id", "")),
        "state": getattr(summary, "state", ""),
    }


__all__ = ["generate"]
