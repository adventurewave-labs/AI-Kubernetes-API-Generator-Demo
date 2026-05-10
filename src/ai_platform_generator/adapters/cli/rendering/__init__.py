"""CLI rendering adapters: the :class:`Renderer` Protocol and concrete impls.

This package owns *all* presentation logic for the CLI adapter. Application
services emit :class:`~ai_platform_generator.domain.events.DomainEvent`\\ s
and call :meth:`Renderer.error` on failure; the renderer chosen by
:func:`build_renderer` is the only place that knows how to translate those
events into bytes on stdout/stderr.

Three concrete strategies are provided:

* :class:`RichRenderer` — TTY default. ANSI / progress bar / panels.
* :class:`JsonRenderer` — CI default (NDJSON, one event per line).
* :class:`QuietRenderer` — emits nothing on stdout; errors to stderr.

The :func:`build_renderer` factory resolves the correct strategy from CLI
options and the environment. See
``docs/ddd/bounded-contexts/05-user-interaction.md`` §5 for the contract.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from .json_renderer import JsonRenderer
from .protocol import Renderer
from .quiet_renderer import QuietRenderer
from .rich_renderer import RichRenderer

_VALID_FORMATS: frozenset[str] = frozenset({"rich", "json", "quiet"})


def _resolve_log_format(opts: dict[str, Any]) -> str:
    """Resolve the active log format string.

    Precedence (highest first):

    1. Explicit ``log_format`` / ``log-format`` key in *opts*.
    2. ``NO_COLOR`` or ``CLICOLOR=0`` env vars → ``"json"`` (no ANSI).
    3. ``sys.stdout.isatty()`` → ``"rich"`` if interactive, else ``"json"``.
    """
    explicit = opts.get("log_format") or opts.get("log-format")
    if explicit:
        fmt = str(explicit).lower()
        if fmt not in _VALID_FORMATS:
            raise ValueError(
                f"Unknown log format {explicit!r}; "
                f"expected one of {sorted(_VALID_FORMATS)}"
            )
        return fmt

    if os.environ.get("NO_COLOR") or os.environ.get("CLICOLOR") == "0":
        return "json"

    isatty = getattr(sys.stdout, "isatty", None)
    if callable(isatty) and isatty():
        return "rich"
    return "json"


def build_renderer(opts: dict[str, Any]) -> Renderer:
    """Build the renderer chosen by *opts* + environment.

    Parameters
    ----------
    opts:
        A flat mapping (typically ``ctx.obj``) carrying CLI flags. The only
        recognised key is ``log_format``; absent / ``None`` triggers
        environment-based auto-detection.
    """
    fmt = _resolve_log_format(opts)
    if fmt == "quiet":
        return QuietRenderer()
    if fmt == "json":
        return JsonRenderer(stream=sys.stdout)
    return RichRenderer()


__all__ = [
    "JsonRenderer",
    "QuietRenderer",
    "Renderer",
    "RichRenderer",
    "build_renderer",
]
