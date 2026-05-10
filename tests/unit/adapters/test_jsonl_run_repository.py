"""Tests for :class:`JsonlRunRepository`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_platform_generator.adapters.run_repository.jsonl import JsonlRunRepository
from ai_platform_generator.domain.aggregates.generation_run import (
    GenerationRun,
    RunState,
)
from ai_platform_generator.domain.values import Intent, RunId


def _intent(text: str = "make me a Database CRD") -> Intent:
    return Intent(text=text, submitted_at=datetime(2026, 5, 10, tzinfo=timezone.utc))


def _run(state: RunState = RunState.PENDING) -> GenerationRun:
    return GenerationRun(
        id=RunId.new(),
        started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        intent=_intent(),
        state=state,
    )


def test_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "runs.jsonl"
    JsonlRunRepository(path)
    assert path.parent.is_dir()


def test_append_then_get_roundtrip(tmp_path: Path) -> None:
    repo = JsonlRunRepository(tmp_path / "runs.jsonl")
    run = _run()
    repo.append(run)

    fetched = repo.get(run.id)
    assert fetched.id == run.id
    assert fetched.state == run.state
    assert fetched.started_at == run.started_at


def test_latest_is_last_appended(tmp_path: Path) -> None:
    repo = JsonlRunRepository(tmp_path / "runs.jsonl")
    a, b, c = _run(), _run(), _run()
    repo.append(a)
    repo.append(b)
    repo.append(c)

    latest = repo.latest()
    assert latest is not None
    assert latest.id == c.id


def test_latest_none_when_empty(tmp_path: Path) -> None:
    repo = JsonlRunRepository(tmp_path / "runs.jsonl")
    assert repo.latest() is None


def test_get_missing_raises_key_error(tmp_path: Path) -> None:
    repo = JsonlRunRepository(tmp_path / "runs.jsonl")
    with pytest.raises(KeyError):
        repo.get(RunId.new())


def test_file_format_is_one_json_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    repo = JsonlRunRepository(path)
    for _ in range(3):
        repo.append(_run())

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert isinstance(parsed, dict)
        # Required keys per the projection.
        assert "run_id" in parsed
        assert "started_at" in parsed
        assert "state" in parsed
        assert "intent_text_hash" in parsed


def test_record_excludes_full_aggregates(tmp_path: Path) -> None:
    """Sanity check: only the projection is on disk; raw text is not."""
    path = tmp_path / "runs.jsonl"
    repo = JsonlRunRepository(path)
    run = _run()
    repo.append(run)

    raw = path.read_text(encoding="utf-8")
    # The raw intent text must not leak — the hash, however, will.
    assert run.intent.text not in raw
    assert run.intent.text_hash() in raw


def test_corrupt_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    repo = JsonlRunRepository(path)
    repo.append(_run())
    # Append an unparseable line.
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not-json\n")
    repo.append(_run())

    # latest still finds the last good record.
    latest = repo.latest()
    assert latest is not None
    assert latest.state == RunState.PENDING


def test_append_uses_o_append_so_concurrent_writers_dont_clobber(tmp_path: Path) -> None:
    """Two repositories writing to the same file must both end up on disk."""
    path = tmp_path / "runs.jsonl"
    repo_a = JsonlRunRepository(path)
    repo_b = JsonlRunRepository(path)

    run_a = _run()
    run_b = _run()
    repo_a.append(run_a)
    repo_b.append(run_b)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    ids = {json.loads(line)["run_id"] for line in lines}
    assert ids == {run_a.id.value, run_b.id.value}
