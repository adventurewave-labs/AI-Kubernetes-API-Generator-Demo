"""Tests for ``ai_platform_generator.domain.values.checksum``."""

from __future__ import annotations

import hashlib

import pytest

from ai_platform_generator.domain.errors import InvalidChecksum
from ai_platform_generator.domain.values.checksum import Checksum

# Well-known SHA-256 of b"hello world".
HELLO_WORLD_SHA256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_of_hello_world_matches_known_value() -> None:
    cs = Checksum.of(b"hello world")
    assert cs.algorithm == "sha256"
    assert cs.value == HELLO_WORLD_SHA256


def test_matches_returns_true_for_same_payload() -> None:
    cs = Checksum.of(b"hello world")
    assert cs.matches(b"hello world") is True


def test_matches_returns_false_for_different_payload() -> None:
    cs = Checksum.of(b"hello world")
    assert cs.matches(b"hello world!") is False


def test_explicit_construction() -> None:
    digest = hashlib.sha256(b"abc").hexdigest()
    cs = Checksum(algorithm="sha256", value=digest)
    assert cs.matches(b"abc")


def test_unsupported_algorithm_rejects() -> None:
    with pytest.raises(InvalidChecksum):
        Checksum(algorithm="md5", value="0" * 64)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0" * 63,  # too short
        "0" * 65,  # too long
        "G" * 64,  # non-hex
        "0" * 64 + " ",
        HELLO_WORLD_SHA256.upper(),  # uppercase rejected
    ],
)
def test_invalid_value_rejects(value: str) -> None:
    with pytest.raises(InvalidChecksum):
        Checksum(algorithm="sha256", value=value)


def test_equality_and_hash() -> None:
    a = Checksum.of(b"x")
    b = Checksum.of(b"x")
    c = Checksum.of(b"y")
    assert a == b
    assert a != c
    assert len({a, b, c}) == 2
