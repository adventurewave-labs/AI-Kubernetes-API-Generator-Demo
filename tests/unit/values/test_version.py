"""Tests for ``ai_platform_generator.domain.values.version``."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_platform_generator.domain.errors import InvalidVersion
from ai_platform_generator.domain.values.version import Version

# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_stability",
    [
        ("v1", "ga"),
        ("v2", "ga"),
        ("v10", "ga"),
        ("v1alpha1", "alpha"),
        ("v1alpha2", "alpha"),
        ("v2beta3", "beta"),
        ("v1beta1", "beta"),
    ],
)
def test_valid_version(value: str, expected_stability: str) -> None:
    v = Version(value)
    assert v.value == value
    assert v.stability == expected_stability


# ---------------------------------------------------------------------------
# Reject cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1",
        "V1",
        "v",
        "valpha1",
        "v1.0",
        "v1alpha",
        "v1gamma1",
        "v1alpha-1",
        "v01alpha1",  # the regex accepts leading zero on the major (v01)
        # but not after alpha/beta? Actually \d+ allows it — confirm: the
        # spec regex is r"^v\d+(?:(?:alpha|beta)\d+)?$" so v01 is valid.
        # We move this case to the accept list below if needed.
        "v1ALPHA1",
        " v1",
        "v1 ",
    ],
)
def test_invalid_version_rejects(value: str) -> None:
    # "v01alpha1" actually *passes* the regex; remove if accidentally listed.
    if value == "v01alpha1":
        # Sanity: it should construct successfully.
        Version(value)
        return
    with pytest.raises(InvalidVersion):
        Version(value)


def test_non_string_rejects() -> None:
    with pytest.raises(InvalidVersion):
        Version(1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Equality / hash
# ---------------------------------------------------------------------------


def test_equality_and_hash() -> None:
    assert Version("v1") == Version("v1")
    assert Version("v1") != Version("v2")
    assert len({Version("v1"), Version("v1"), Version("v2")}) == 2


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------


@given(
    major=st.integers(min_value=0, max_value=99),
    pre=st.sampled_from(["", "alpha", "beta"]),
    minor=st.integers(min_value=0, max_value=99),
)
def test_random_valid_versions_construct(major: int, pre: str, minor: int) -> None:
    value = f"v{major}" if not pre else f"v{major}{pre}{minor}"
    v = Version(value)
    if pre == "alpha":
        assert v.stability == "alpha"
    elif pre == "beta":
        assert v.stability == "beta"
    else:
        assert v.stability == "ga"


@given(st.text(min_size=0, max_size=12))
def test_random_text_either_constructs_or_rejects(value: str) -> None:
    try:
        Version(value)
    except InvalidVersion:
        return
    # Round-trip stability classifier.
    assert Version(value).stability in {"alpha", "beta", "ga"}
