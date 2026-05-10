"""Tests for :class:`ChainSecretProvider`."""

from __future__ import annotations

from ai_platform_generator.adapters.secrets.chain import ChainSecretProvider
from ai_platform_generator.adapters.secrets.in_memory import InMemorySecretProvider


def test_first_provider_wins() -> None:
    a = InMemorySecretProvider({"K": "from-a"})
    b = InMemorySecretProvider({"K": "from-b"})
    chain = ChainSecretProvider([a, b])
    assert chain.get("K") == "from-a"


def test_falls_through_on_none() -> None:
    a = InMemorySecretProvider({"OTHER": "x"})
    b = InMemorySecretProvider({"K": "from-b"})
    chain = ChainSecretProvider([a, b])
    assert chain.get("K") == "from-b"


def test_returns_none_when_no_provider_has_value() -> None:
    chain = ChainSecretProvider(
        [InMemorySecretProvider(), InMemorySecretProvider({"OTHER": "x"})]
    )
    assert chain.get("MISSING") is None


def test_names_is_sorted_union() -> None:
    a = InMemorySecretProvider({"A": "1", "B": "2"})
    b = InMemorySecretProvider({"B": "2", "C": "3"})
    chain = ChainSecretProvider([a, b])
    assert chain.names() == ["A", "B", "C"]


def test_empty_chain() -> None:
    chain = ChainSecretProvider([])
    assert chain.get("ANY") is None
    assert chain.names() == []


def test_iterable_consumed_once() -> None:
    """A generator argument must not break later calls."""
    a = InMemorySecretProvider({"K": "v"})
    chain = ChainSecretProvider(p for p in [a])
    assert chain.get("K") == "v"
    assert chain.get("K") == "v"
    assert chain.names() == ["K"]
