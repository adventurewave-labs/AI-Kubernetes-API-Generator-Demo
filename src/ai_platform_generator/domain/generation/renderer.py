"""Jinja2-backed ``Renderer`` domain service.

Thin wrapper that pins the configuration we want everywhere:

* ``StrictUndefined`` — missing context variables raise *during render*
  rather than producing a silent empty string. This is what ADR-0015
  requires so template bugs surface in unit tests.
* ``keep_trailing_newline=True`` — POSIX-friendly file output.
* ``autoescape=False`` — we render YAML / Go / Markdown, never HTML.

Custom filters can be registered through :meth:`Renderer.register_filter`;
generators may need e.g. a YAML-quoting or Go-identifier filter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from ai_platform_generator.domain.errors import TemplateRenderingError


class Renderer:
    """Render Jinja2 templates with strict, deterministic defaults."""

    def __init__(self, searchpath: Path) -> None:
        if not isinstance(searchpath, Path):
            raise TypeError(
                f"searchpath must be a Path, got {type(searchpath).__name__}"
            )
        if not searchpath.exists():
            raise FileNotFoundError(
                f"renderer searchpath does not exist: {searchpath}"
            )
        if not searchpath.is_dir():
            raise NotADirectoryError(
                f"renderer searchpath is not a directory: {searchpath}"
            )

        self._searchpath = searchpath
        self._env = Environment(
            loader=FileSystemLoader(str(searchpath)),
            autoescape=False,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    @property
    def searchpath(self) -> Path:
        """Directory in which templates are looked up."""
        return self._searchpath

    def register_filter(self, name: str, fn: Callable[..., Any]) -> None:
        """Register ``fn`` as a Jinja filter named ``name``.

        Existing filters with the same name are overwritten — generators
        register filters at construction time so this is normally fine.
        """
        if not isinstance(name, str) or not name:
            raise ValueError(f"filter name must be a non-empty str, got {name!r}")
        if not callable(fn):
            raise TypeError(f"filter fn must be callable, got {type(fn).__name__}")
        self._env.filters[name] = fn

    def render(self, template_name: str, context: Mapping[str, Any]) -> str:
        """Load ``template_name`` from the searchpath and render it.

        Wraps any Jinja error in :class:`TemplateRenderingError` so
        callers can catch a single domain-typed exception.
        """
        try:
            template = self._env.get_template(template_name)
            return template.render(**dict(context))
        except TemplateError as exc:
            raise TemplateRenderingError(
                f"failed to render template {template_name!r}: {exc}"
            ) from exc
