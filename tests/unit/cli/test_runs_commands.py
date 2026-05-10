"""Tests for ``main runs list`` and ``main runs show <id>``.

A :class:`JsonlRunRepository` is pre-populated under ``tmp_path`` and
the ``runs_log_path`` is forced via ``--runs-log`` *or* by patching
``AppConfig`` to use the temp file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ai_platform_generator.adapters.cli.main import main
from ai_platform_generator.adapters.run_repository.jsonl import (
    JsonlRunRepository,
)
from ai_platform_generator.domain.aggregates.generation_run import (
    GenerationRun,
    RunState,
)
from ai_platform_generator.domain.values import Intent, RunId

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner


@pytest.fixture
def runs_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[RunId]]:
    """Pre-populate ``runs.jsonl`` with two distinct runs and patch composition."""
    log_path = tmp_path / "runs.jsonl"
    repo = JsonlRunRepository(path=log_path)

    ids: list[RunId] = []
    for _ in range(2):
        rid = RunId.new()
        ids.append(rid)
        run = GenerationRun(
            id=rid,
            started_at=datetime.now(timezone.utc),
            intent=Intent(
                text=f"intent for {rid.value}",
                submitted_at=datetime.now(timezone.utc),
            ),
            state=RunState.SUCCEEDED,
        )
        repo.append(run)

    # Patch JsonlRunRepository at its public import point so any
    # caller that constructs one without a path argument still picks up
    # our temp file. Patch *both* the source module attribute and the
    # adapter package re-export so the CLI sees the fixture.
    from ai_platform_generator.adapters.run_repository import (
        jsonl as jsonl_module,
    )

    real_cls = jsonl_module.JsonlRunRepository

    class _RedirectedRepo(real_cls):  # type: ignore[misc, valid-type]
        def __init__(self, path: Path | None = None) -> None:
            super().__init__(path=log_path)

    monkeypatch.setattr(jsonl_module, "JsonlRunRepository", _RedirectedRepo)
    from ai_platform_generator.adapters import (
        run_repository as run_repository_pkg,
    )

    monkeypatch.setattr(
        run_repository_pkg, "JsonlRunRepository", _RedirectedRepo, raising=False
    )

    return log_path, ids


def test_runs_list_shows_all_run_ids(
    cli_runner: CliRunner, runs_repo: tuple[Path, list[RunId]]
) -> None:
    _log_path, ids = runs_repo
    result = cli_runner.invoke(main, ["runs", "list"])

    assert result.exit_code == 0, result.stderr or result.stdout
    combined = result.stdout + result.stderr
    for rid in ids:
        assert rid.value in combined, (
            f"run id {rid.value!r} missing from output: {combined!r}"
        )


def test_runs_show_renders_record(
    cli_runner: CliRunner, runs_repo: tuple[Path, list[RunId]]
) -> None:
    _log_path, ids = runs_repo
    target = ids[0].value

    result = cli_runner.invoke(main, ["runs", "show", target])

    assert result.exit_code == 0, result.stderr or result.stdout

    combined = result.stdout + result.stderr
    assert target in combined
    # The persisted record always carries a state — accept JSON or
    # plain-text rendering.
    assert any(
        token in combined for token in ("succeeded", "state", "started_at")
    ), f"record fields missing from output: {combined!r}"

    # If the renderer chose JSON, the GVK / state should round-trip.
    for line in combined.splitlines():
        try:
            obj = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("run_id") == target:
            assert "state" in obj
            break
