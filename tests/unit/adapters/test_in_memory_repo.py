"""Tests for :class:`InMemoryArtifactRepository`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from ai_platform_generator.adapters.repo.in_memory import InMemoryArtifactRepository


@dataclass(frozen=True)
class _StubBundle:
    """Minimal stand-in for the eventual ``ArtifactBundle`` aggregate.

    The repository only requires that the bundle exposes a ``run_id``
    attribute. Once Phase 3 lands the real aggregate, these tests can be
    re-pointed at it without further changes.
    """

    run_id: Any
    payload: str = ""


def test_save_then_load_roundtrip() -> None:
    repo = InMemoryArtifactRepository()
    bundle = _StubBundle(run_id="run-1", payload="hello")

    repo.save(bundle)

    assert repo.exists("run-1") is True
    assert repo.load("run-1") is bundle


def test_save_is_idempotent_on_run_id() -> None:
    repo = InMemoryArtifactRepository()
    first = _StubBundle(run_id="run-1", payload="v1")
    second = _StubBundle(run_id="run-1", payload="v2")

    repo.save(first)
    repo.save(second)

    assert len(repo) == 1
    assert repo.load("run-1") is second


def test_load_missing_raises_key_error() -> None:
    repo = InMemoryArtifactRepository()

    with pytest.raises(KeyError):
        repo.load("absent")


def test_exists_false_when_empty() -> None:
    repo = InMemoryArtifactRepository()
    assert repo.exists("anything") is False
    assert len(repo) == 0
