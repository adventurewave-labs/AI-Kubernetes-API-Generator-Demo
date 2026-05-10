"""Tests for ``ai_platform_generator.domain.values.kind``."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_platform_generator.domain.errors import InvalidKind
from ai_platform_generator.domain.values.kind import Kind

# ---------------------------------------------------------------------------
# Happy path + plural / singular
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,plural,singular",
    [
        ("Database", "databases", "database"),
        ("PostgresCluster", "postgresclusters", "postgrescluster"),
        ("Bus", "buses", "bus"),
        ("Policy", "policies", "policy"),
        ("Class", "classes", "class"),
        ("VectorDB", "vectordbs", "vectordb"),
        # 1-letter and trailing-digit cases.
        ("A", "as", "a"),
        ("App2", "app2s", "app2"),
        ("S3", "s3s", "s3"),
        # Trailing 's' takes the 'es' branch.
        ("Cross", "crosses", "cross"),
    ],
)
def test_valid_kind_plural_singular(value: str, plural: str, singular: str) -> None:
    k = Kind(value)
    assert k.value == value
    assert k.plural == plural
    assert k.singular == singular


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "",
        "lowercase",
        "1Leading",
        "_Foo",
        "Foo Bar",
        "Foo-Bar",
        "Foo_Bar",
        "Foo.Bar",
    ],
)
def test_invalid_kind_rejects(value: str) -> None:
    with pytest.raises(InvalidKind):
        Kind(value)


def test_non_string_rejects() -> None:
    with pytest.raises(InvalidKind):
        Kind(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Equality / hash / frozen
# ---------------------------------------------------------------------------


def test_equality_and_hash() -> None:
    assert Kind("Foo") == Kind("Foo")
    assert Kind("Foo") != Kind("Bar")
    assert len({Kind("A"), Kind("A"), Kind("B")}) == 2


def test_frozen() -> None:
    k = Kind("Foo")
    with pytest.raises((AttributeError, TypeError)):
        k.value = "Bar"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------


@given(st.from_regex(r"\A[A-Z][A-Za-z0-9]{0,15}\Z", fullmatch=True))
def test_random_valid_kinds_construct(value: str) -> None:
    k = Kind(value)
    assert k.singular == value.lower()
    # Plural ends with one of our suffix shapes.
    assert k.plural.endswith(("s", "es", "ies"))


@given(st.text(min_size=0, max_size=15))
def test_random_text_either_constructs_or_rejects(value: str) -> None:
    try:
        Kind(value)
    except InvalidKind:
        return
    assert value[:1].isupper()
    assert all(c.isalnum() for c in value)
