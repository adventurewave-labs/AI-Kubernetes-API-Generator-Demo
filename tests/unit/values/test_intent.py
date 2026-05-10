"""Tests for ``ai_platform_generator.domain.values.intent``."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from ai_platform_generator.domain.errors import InvalidIntent
from ai_platform_generator.domain.values.intent import Intent

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_basic_intent_constructs() -> None:
    i = Intent(text="give me a postgres cluster", submitted_at=NOW)
    assert i.text == "give me a postgres cluster"
    assert i.submitted_at == NOW


def test_text_hash_is_sha256_of_text() -> None:
    text = "deploy a redis"
    i = Intent(text=text, submitted_at=NOW)
    assert i.text_hash() == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_text_hash_changes_with_text() -> None:
    a = Intent(text="a", submitted_at=NOW).text_hash()
    b = Intent(text="b", submitted_at=NOW).text_hash()
    assert a != b


@pytest.mark.parametrize("text", ["", "   ", "\t\n  "])
def test_empty_or_whitespace_rejects(text: str) -> None:
    with pytest.raises(InvalidIntent):
        Intent(text=text, submitted_at=NOW)


def test_too_long_rejects() -> None:
    with pytest.raises(InvalidIntent):
        Intent(text="x" * 8193, submitted_at=NOW)


def test_max_length_at_boundary_ok() -> None:
    Intent(text="x" * 8192, submitted_at=NOW)


def test_non_string_text_rejects() -> None:
    with pytest.raises(InvalidIntent):
        Intent(text=123, submitted_at=NOW)  # type: ignore[arg-type]


def test_non_datetime_submitted_at_rejects() -> None:
    with pytest.raises(InvalidIntent):
        Intent(text="hi", submitted_at="2026-01-01")  # type: ignore[arg-type]


def test_equality_and_hash() -> None:
    a = Intent(text="x", submitted_at=NOW)
    b = Intent(text="x", submitted_at=NOW)
    c = Intent(text="y", submitted_at=NOW)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
