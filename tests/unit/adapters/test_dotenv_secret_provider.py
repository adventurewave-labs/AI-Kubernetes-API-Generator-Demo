"""Tests for :class:`DotenvSecretProvider`.

Asserts the adapter does **not** mutate :data:`os.environ` — that is the
reason we use ``dotenv_values`` instead of ``load_dotenv``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_platform_generator.adapters.secrets.dotenv import DotenvSecretProvider


def _write_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_reads_values_from_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _write_env(
        env_file,
        "OPENAI_API_KEY=sk-test\nGITHUB_TOKEN=ghp_y\n# a comment\n",
    )
    provider = DotenvSecretProvider(env_file)
    assert provider.get("OPENAI_API_KEY") == "sk-test"
    assert provider.get("GITHUB_TOKEN") == "ghp_y"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _write_env(env_file, "FOO=bar\n")
    provider = DotenvSecretProvider(env_file)
    assert provider.get("UNSET") is None


def test_missing_file_treated_as_empty(tmp_path: Path) -> None:
    provider = DotenvSecretProvider(tmp_path / "nope.env")
    assert provider.get("ANYTHING") is None
    assert provider.names() == []


def test_does_not_mutate_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOTENV_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    _write_env(env_file, "DOTENV_TEST_KEY=local-only\n")

    provider = DotenvSecretProvider(env_file)
    assert provider.get("DOTENV_TEST_KEY") == "local-only"
    # Critical: os.environ must remain pristine.
    assert "DOTENV_TEST_KEY" not in os.environ


def test_names_returns_sorted_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _write_env(env_file, "B=2\nA=1\nC=3\n")
    provider = DotenvSecretProvider(env_file)
    assert provider.names() == ["A", "B", "C"]


def test_lazy_read(tmp_path: Path) -> None:
    """File is read on first access, not at construction."""
    env_file = tmp_path / ".env"
    provider = DotenvSecretProvider(env_file)
    # Construct first, then create the file — the provider should pick
    # it up on the first ``get`` call.
    _write_env(env_file, "K=v\n")
    assert provider.get("K") == "v"


def test_default_path_is_dot_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_env(tmp_path / ".env", "DEFAULT_KEY=present\n")
    provider = DotenvSecretProvider()
    assert provider.get("DEFAULT_KEY") == "present"
