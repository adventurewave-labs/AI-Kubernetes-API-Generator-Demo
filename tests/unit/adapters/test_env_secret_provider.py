"""Tests for :class:`EnvSecretProvider`."""

from __future__ import annotations

import re

import pytest

from ai_platform_generator.adapters.secrets.env import (
    DEFAULT_NAME_PATTERN,
    EnvSecretProvider,
)


def test_get_returns_value_from_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = EnvSecretProvider()
    assert provider.get("OPENAI_API_KEY") == "sk-test"


def test_get_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    provider = EnvSecretProvider()
    assert provider.get("DEFINITELY_NOT_SET") is None


def test_names_returns_secret_shaped_envvars(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_env: dict[str, str] = {
        "OPENAI_API_KEY": "sk-1",
        "GITHUB_TOKEN": "ghp_x",
        "MY_APP_SECRET": "y",
        "PATH": "/bin:/usr/bin",
        "HOME": "/home/u",
    }
    provider = EnvSecretProvider(environ=fake_env)
    names = provider.names()
    assert names == ["GITHUB_TOKEN", "MY_APP_SECRET", "OPENAI_API_KEY"]


def test_default_pattern_anchors_suffix() -> None:
    # Sanity-check the default regex: requires a suffix match.
    assert DEFAULT_NAME_PATTERN.fullmatch("OPENAI_API_KEY")
    assert DEFAULT_NAME_PATTERN.fullmatch("FOO_TOKEN")
    assert DEFAULT_NAME_PATTERN.fullmatch("BAR_SECRET")
    assert DEFAULT_NAME_PATTERN.fullmatch("PATH") is None
    assert DEFAULT_NAME_PATTERN.fullmatch("FOO_TOKEN_SUFFIX") is None


def test_custom_pattern_via_string() -> None:
    fake_env = {"WEIRD_KEY_FORMAT": "x", "FOO": "y"}
    provider = EnvSecretProvider(pattern=r".*_FORMAT$", environ=fake_env)
    assert provider.names() == ["WEIRD_KEY_FORMAT"]


def test_custom_pattern_via_compiled() -> None:
    fake_env = {"X_KEY": "x", "Y_KEY": "y", "OTHER": "z"}
    pattern = re.compile(r".*_KEY$")
    provider = EnvSecretProvider(pattern=pattern, environ=fake_env)
    assert provider.names() == ["X_KEY", "Y_KEY"]
