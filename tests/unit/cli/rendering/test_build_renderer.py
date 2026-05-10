"""Unit tests for the :func:`build_renderer` factory and ``_resolve_log_format``."""
from __future__ import annotations

import sys

import pytest

from ai_platform_generator.adapters.cli.rendering import (
    JsonRenderer,
    QuietRenderer,
    RichRenderer,
    _resolve_log_format,
    build_renderer,
)


@pytest.fixture(autouse=True)
def _clear_color_envs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip colour-env vars so each test starts from a known baseline."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR", raising=False)


def _force_isatty(monkeypatch: pytest.MonkeyPatch, *, value: bool) -> None:
    monkeypatch.setattr(
        sys.stdout, "isatty", lambda: value, raising=False
    )


def test_explicit_quiet_returns_quiet_renderer() -> None:
    renderer = build_renderer({"log_format": "quiet"})
    assert isinstance(renderer, QuietRenderer)


def test_explicit_json_returns_json_renderer() -> None:
    renderer = build_renderer({"log_format": "json"})
    assert isinstance(renderer, JsonRenderer)


def test_explicit_rich_returns_rich_renderer() -> None:
    renderer = build_renderer({"log_format": "rich"})
    assert isinstance(renderer, RichRenderer)


def test_unknown_format_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="Unknown log format"):
        build_renderer({"log_format": "yaml"})


def test_isatty_default_picks_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_isatty(monkeypatch, value=True)
    renderer = build_renderer({"log_format": None})
    assert isinstance(renderer, RichRenderer)


def test_no_isatty_default_picks_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_isatty(monkeypatch, value=False)
    renderer = build_renderer({"log_format": None})
    assert isinstance(renderer, JsonRenderer)


def test_no_color_env_forces_json_in_auto_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_isatty(monkeypatch, value=True)
    monkeypatch.setenv("NO_COLOR", "1")
    renderer = build_renderer({})
    assert isinstance(renderer, JsonRenderer)


def test_clicolor_zero_forces_json_in_auto_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_isatty(monkeypatch, value=True)
    monkeypatch.setenv("CLICOLOR", "0")
    renderer = build_renderer({})
    assert isinstance(renderer, JsonRenderer)


def test_explicit_rich_with_no_color_propagates_to_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    renderer = build_renderer({"log_format": "rich"})
    assert isinstance(renderer, RichRenderer)
    # Rich's ``Console`` honours ``no_color``.
    assert renderer.console.no_color is True


def test_resolve_log_format_accepts_dashed_key() -> None:
    assert _resolve_log_format({"log-format": "quiet"}) == "quiet"


def test_resolve_log_format_is_case_insensitive() -> None:
    assert _resolve_log_format({"log_format": "JSON"}) == "json"
