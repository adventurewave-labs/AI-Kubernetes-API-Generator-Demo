"""Click ``main`` group for the ``ai-platform-generator`` CLI.

This is the entry point referenced by the ``ai-platform-generator``
console-script in ``pyproject.toml``. It owns:

* the top-level Click group and its **global options**
  (``docs/ddd/bounded-contexts/05-user-interaction.md`` §4);
* the renderer-resolution helper ``_resolve_log_format`` (auto-detect
  TTY vs non-TTY when ``--log-format`` is unset);
* the lazy renderer wiring that delegates to Agent Q's
  :mod:`ai_platform_generator.adapters.cli.rendering` package — the
  module is importable even before that package lands by falling back
  to a tiny inline ``_PrintRenderer`` so ``--help`` still works.

Sub-commands (one per file under ``commands/``) are bound at the
bottom. They consume shared state via ``ctx.obj["opts"]`` and
``ctx.obj["renderer"]``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from ai_platform_generator import __version__

from .commands import (
    build,
    cluster,
    examples,
    generate,
    interactive,
    runs,
    validate,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import GenerationSummary
    from ai_platform_generator.domain.errors import PlatformGeneratorError
    from ai_platform_generator.domain.events import DomainEvent


# ---------------------------------------------------------------------------
# Renderer helpers
# ---------------------------------------------------------------------------


class _PrintRenderer:
    """Last-resort renderer used when Agent Q's package is unavailable.

    Implements the minimum surface of the Renderer Protocol so the CLI
    is operational in dev environments where the rendering package has
    not yet been wired in. Output is intentionally minimal — Agent Q's
    real renderers replace this in production.
    """

    def __init__(self, log_format: str = "tty") -> None:
        self._log_format = log_format

    def begin(self) -> None:  # pragma: no cover - trivial
        return None

    def event(self, event: DomainEvent) -> None:  # pragma: no cover - trivial
        # Touch the attribute to force evaluation; suppress otherwise.
        getattr(event, "name", "")

    def end(self, summary: GenerationSummary) -> None:  # pragma: no cover - trivial
        click.echo(f"run {summary.run_id} finished ({summary.state})")

    def error(self, error: PlatformGeneratorError | BaseException) -> int:
        # Lazy import to keep this fallback module-load cheap.
        from .exit_codes import code_for

        click.echo(f"error: {error}", err=True)
        return code_for(error)


def _resolve_log_format(opts: dict[str, Any]) -> str:
    """Resolve the effective ``--log-format`` value.

    Honours an explicit ``opts["log_format"]`` if set; otherwise
    auto-detects from the stdout TTY state — non-TTY → ``"json"``,
    TTY → ``"tty"``. The "quiet" mode is opt-in only.
    """
    explicit = opts.get("log_format")
    if explicit:
        return str(explicit)
    if not sys.stdout.isatty():
        return "json"
    return "tty"


def _build_renderer(opts: dict[str, Any]) -> Any:
    """Build the Renderer for this invocation.

    Delegates to Agent Q's ``adapters.cli.rendering`` package when
    available; falls back to :class:`_PrintRenderer` if the package
    has not yet landed so ``--help`` and ``--version`` still work.

    The CLI exposes ``--log-format`` with values ``tty / json / quiet``
    while Q's package uses ``rich / json / quiet`` internally. We
    translate here so the public CLI surface stays stable.
    """
    log_format = _resolve_log_format(opts)
    try:
        from .rendering import build_renderer as _build
    except ImportError:
        return _PrintRenderer(log_format=log_format)

    # Translate the CLI-facing ``tty`` value into Q's ``rich``.
    forwarded = dict(opts)
    if log_format == "tty":
        forwarded["log_format"] = "rich"
    else:
        forwarded["log_format"] = log_format

    try:
        return _build(forwarded)
    except Exception:
        # Defensive: if Q's package raises during construction, do not
        # take the entire CLI down — the user still needs to see help
        # text and a remediation hint.
        return _PrintRenderer(log_format=log_format)


# ---------------------------------------------------------------------------
# Click ``main`` group
# ---------------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="ai-platform-generator")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Where artefacts land (default ./generated_specs/<kind>).",
)
@click.option(
    "--no-deploy",
    "deploy",
    flag_value=False,
    default=True,
    help="Skip cluster deployment.",
)
@click.option(
    "--deploy",
    "deploy",
    flag_value=True,
    default=True,
    help="Deploy to cluster after generation (default).",
)
@click.option(
    "--no-fallback",
    "allow_demo_mode",
    flag_value=False,
    default=True,
    help="Disable Demo Mode fallback (CI-friendly).",
)
@click.option(
    "--api-key",
    envvar="OPENROUTER_API_KEY",
    default=None,
    help="LLM provider API key.",
)
@click.option(
    "--model",
    envvar="OPENROUTER_MODEL",
    default="meta-llama/llama-3.2-3b-instruct:free",
    help="LLM model id.",
)
@click.option(
    "--llm-provider",
    type=click.Choice(["openrouter", "openai", "demo", "fake"]),
    default="openrouter",
    show_default=True,
    help="Which LLM adapter to wire into the orchestrator.",
)
@click.option(
    "--log-format",
    type=click.Choice(["tty", "json", "quiet"]),
    default=None,
    help="Output format. Auto-detected from TTY by default.",
)
@click.option("--debug/--no-debug", default=False, help="Verbose logging.")
@click.option("--otel/--no-otel", default=False, help="Enable OpenTelemetry sink.")
@click.option(
    "--cluster-name",
    default="ai-platform-demo",
    show_default=True,
    help="Name of the kind cluster to ensure / deploy into.",
)
@click.option(
    "--load-env/--no-load-env",
    default=False,
    help="Load secrets from .env in cwd.",
)
@click.pass_context
def main(ctx: click.Context, /, **opts: Any) -> None:
    """AI Kubernetes API Generator — natural language → CRDs."""
    ctx.ensure_object(dict)
    ctx.obj["opts"] = opts
    ctx.obj["renderer"] = _build_renderer(opts)


main.add_command(generate)
main.add_command(interactive)
main.add_command(build)
main.add_command(examples)
main.add_command(cluster)
main.add_command(validate)
main.add_command(runs)


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - script invocation
    main()
