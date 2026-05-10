"""Tests for :class:`Renderer` (Jinja2 wrapper)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_platform_generator.domain.errors import TemplateRenderingError
from ai_platform_generator.domain.generation.renderer import Renderer


def _write(template_dir: Path, name: str, body: str) -> None:
    (template_dir / name).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def test_renderer_rejects_non_path(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="searchpath must be a Path"):
        Renderer(searchpath=str(tmp_path))  # type: ignore[arg-type]


def test_renderer_rejects_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        Renderer(searchpath=missing)


def test_renderer_rejects_file_path(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hi")
    with pytest.raises(NotADirectoryError):
        Renderer(searchpath=f)


def test_renderer_exposes_searchpath(tmp_path: Path) -> None:
    r = Renderer(searchpath=tmp_path)
    assert r.searchpath == tmp_path


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def test_render_succeeds_with_full_context(tmp_path: Path) -> None:
    _write(tmp_path, "greet.j2", "hello {{ name }}!\n")
    r = Renderer(searchpath=tmp_path)
    out = r.render("greet.j2", {"name": "world"})
    assert out == "hello world!\n"  # keep_trailing_newline=True


def test_render_keeps_trailing_newline(tmp_path: Path) -> None:
    _write(tmp_path, "with-newline.j2", "first\nsecond\n")
    r = Renderer(searchpath=tmp_path)
    assert r.render("with-newline.j2", {}).endswith("\n")


def test_render_does_not_autoescape_html(tmp_path: Path) -> None:
    """We render YAML/Go — never HTML — so '<' must come through unescaped."""
    _write(tmp_path, "raw.j2", "{{ value }}")
    r = Renderer(searchpath=tmp_path)
    assert r.render("raw.j2", {"value": "<not-html>&"}) == "<not-html>&"


def test_render_strict_undefined_raises(tmp_path: Path) -> None:
    _write(tmp_path, "missing.j2", "value: {{ missing_var }}\n")
    r = Renderer(searchpath=tmp_path)
    with pytest.raises(TemplateRenderingError) as exc_info:
        r.render("missing.j2", {})
    # The original Jinja error must be chained for diagnostics.
    assert exc_info.value.__cause__ is not None


def test_render_missing_template_raises_domain_error(tmp_path: Path) -> None:
    r = Renderer(searchpath=tmp_path)
    with pytest.raises(TemplateRenderingError):
        r.render("does-not-exist.j2", {})


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------
def test_register_filter_makes_filter_available(tmp_path: Path) -> None:
    _write(tmp_path, "pluralise.j2", "{{ word | plural }}\n")
    r = Renderer(searchpath=tmp_path)
    r.register_filter("plural", lambda s: s + "s")
    assert r.render("pluralise.j2", {"word": "cluster"}) == "clusters\n"


def test_register_filter_rejects_empty_name(tmp_path: Path) -> None:
    r = Renderer(searchpath=tmp_path)
    with pytest.raises(ValueError, match="filter name must be a non-empty str"):
        r.register_filter("", lambda x: x)


def test_register_filter_rejects_non_callable(tmp_path: Path) -> None:
    r = Renderer(searchpath=tmp_path)
    with pytest.raises(TypeError, match="filter fn must be callable"):
        r.register_filter("bad", "not-callable")  # type: ignore[arg-type]


def test_register_filter_overwrite_uses_latest(tmp_path: Path) -> None:
    _write(tmp_path, "f.j2", "{{ x | tag }}")
    r = Renderer(searchpath=tmp_path)
    r.register_filter("tag", lambda s: f"[{s}]")
    r.register_filter("tag", lambda s: f"<{s}>")
    assert r.render("f.j2", {"x": "v"}) == "<v>"
