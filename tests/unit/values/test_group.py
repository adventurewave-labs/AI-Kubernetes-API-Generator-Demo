"""Tests for ``ai_platform_generator.domain.values.group``."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_platform_generator.domain.errors import InvalidGroup
from ai_platform_generator.domain.values.group import Group

# ---------------------------------------------------------------------------
# Happy-path / accept cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "platform.example.com",
        "database.cnoe.io",
        "a.b",
        "abc.def-ghi",
        "1.2",
        "foo-bar.baz-qux",
        "a.b.c",  # multiple dots OK as long as regex matches
    ],
)
def test_valid_group_constructs(value: str) -> None:
    g = Group(value)
    assert g.value == value
    assert str(g) == value


# ---------------------------------------------------------------------------
# Reject cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "",
        "no-dot",
        "UPPER.case",
        ".leading",
        "trailing.",
        "double..dot",
        "spaces in.it",
        "with_underscore.dot",
        "tab\there.dot",
    ],
)
def test_invalid_group_rejects(value: str) -> None:
    with pytest.raises(InvalidGroup):
        Group(value)


def test_non_string_rejects() -> None:
    with pytest.raises(InvalidGroup):
        Group(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Equality / hash
# ---------------------------------------------------------------------------


def test_equality_by_value() -> None:
    assert Group("platform.example.com") == Group("platform.example.com")
    assert Group("a.b") != Group("a.c")


def test_hashable() -> None:
    s = {Group("a.b"), Group("a.b"), Group("c.d")}
    assert len(s) == 2


def test_frozen_immutable() -> None:
    g = Group("a.b")
    with pytest.raises((AttributeError, TypeError)):
        g.value = "c.d"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------


# Build random valid group strings: two non-empty runs of [a-z0-9-]
# joined by a single dot. Avoid leading/trailing/double dots.
_segment = st.from_regex(r"\A[a-z0-9-]{1,16}\Z", fullmatch=True)


@given(left=_segment, right=_segment)
def test_random_valid_inputs_construct(left: str, right: str) -> None:
    value = f"{left}.{right}"
    # Skip pathological cases the generator can produce that the
    # explicit double-dot/leading-dot guard rejects.
    if ".." in value or value.startswith(".") or value.endswith("."):
        return
    Group(value)


@given(st.text(min_size=0, max_size=20))
def test_random_text_either_constructs_or_rejects(value: str) -> None:
    try:
        Group(value)
    except InvalidGroup:
        return
    # If we got here the constructor accepted it — confirm the regex shape.
    assert "." in value
    assert value == value.lower()
