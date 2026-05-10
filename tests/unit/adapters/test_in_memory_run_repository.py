"""Tests for :class:`InMemoryRunRepository`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_platform_generator.adapters.run_repository.in_memory import (
    InMemoryRunRepository,
)
from ai_platform_generator.domain.values import RunId


def _make_run(rid: RunId | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=rid or RunId.new(), state="pending")


def test_append_and_get_round_trip() -> None:
    repo = InMemoryRunRepository()
    run = _make_run()
    repo.append(run)

    assert repo.get(run.id) is run


def test_latest_returns_most_recent_append() -> None:
    repo = InMemoryRunRepository()
    a, b, c = _make_run(), _make_run(), _make_run()
    repo.append(a)
    repo.append(b)
    repo.append(c)

    assert repo.latest() is c


def test_latest_is_none_when_empty() -> None:
    assert InMemoryRunRepository().latest() is None


def test_get_raises_for_missing_run() -> None:
    repo = InMemoryRunRepository()
    with pytest.raises(KeyError):
        repo.get(RunId.new())


def test_append_is_idempotent_per_id() -> None:
    repo = InMemoryRunRepository()
    rid = RunId.new()
    repo.append(SimpleNamespace(id=rid, state="pending"))
    repo.append(SimpleNamespace(id=rid, state="succeeded"))

    assert len(repo) == 1
    assert repo.get(rid).state == "succeeded"


def test_all_returns_runs_in_insertion_order() -> None:
    repo = InMemoryRunRepository()
    runs = [_make_run() for _ in range(3)]
    for r in runs:
        repo.append(r)

    assert repo.all() == runs
