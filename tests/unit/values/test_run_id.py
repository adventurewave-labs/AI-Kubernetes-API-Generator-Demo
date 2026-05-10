"""Tests for ``ai_platform_generator.domain.values.run_id``."""

from __future__ import annotations

import uuid

import pytest

from ai_platform_generator.domain.errors import InvalidRunId
from ai_platform_generator.domain.values.run_id import RunId


def test_new_returns_unique_runids() -> None:
    a = RunId.new()
    b = RunId.new()
    assert a != b
    # Round-trippable through uuid.UUID.
    assert uuid.UUID(a.value)
    assert uuid.UUID(b.value)


def test_explicit_uuid_v4_accepts() -> None:
    val = str(uuid.uuid4())
    r = RunId(val)
    assert r.value == val


def test_braced_form_normalised() -> None:
    val = uuid.uuid4()
    r = RunId(f"{{{val}}}")
    assert r.value == str(val)


@pytest.mark.parametrize(
    "value",
    ["", "not-a-uuid", "1234", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],
)
def test_invalid_string_rejects(value: str) -> None:
    with pytest.raises(InvalidRunId):
        RunId(value)


def test_non_string_rejects() -> None:
    with pytest.raises(InvalidRunId):
        RunId(123)  # type: ignore[arg-type]


def test_equality_and_hash() -> None:
    val = str(uuid.uuid4())
    a = RunId(val)
    b = RunId(val)
    assert a == b
    assert hash(a) == hash(b)
