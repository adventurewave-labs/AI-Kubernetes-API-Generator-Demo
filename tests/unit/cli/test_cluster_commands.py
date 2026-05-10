"""Tests for ``main cluster ensure|status|teardown``.

These commands wrap :class:`KindClusterRuntime`. We monkey-patch the
runtime to :class:`FakeClusterRuntime` so they run without a real Kind
binary or container runtime.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from ai_platform_generator.adapters.cli.main import main
from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime

if TYPE_CHECKING:  # pragma: no cover - typing only
    from click.testing import CliRunner


@pytest.fixture
def patched_kind_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> FakeClusterRuntime:
    """Replace the production :class:`KindClusterRuntime` with the fake.

    The cluster commands import the runtime lazily at command time
    (Agent P's territory) so we patch the symbol on its source module.
    """
    fake = FakeClusterRuntime()

    from ai_platform_generator.adapters.runtime import kind as kind_module

    def _factory(*_args, **_kwargs) -> FakeClusterRuntime:
        return fake

    monkeypatch.setattr(kind_module, "KindClusterRuntime", _factory)
    # Some callers also import via the package root.
    from ai_platform_generator.adapters import runtime as runtime_pkg

    monkeypatch.setattr(
        runtime_pkg, "KindClusterRuntime", _factory, raising=False
    )
    return fake


def test_cluster_ensure_succeeds(
    cli_runner: CliRunner, patched_kind_runtime: FakeClusterRuntime
) -> None:
    result = cli_runner.invoke(main, ["cluster", "ensure", "foo"])
    assert result.exit_code == 0, result.stderr or result.stdout
    combined = (result.stdout + result.stderr).lower()
    # Accept either the documented "Cluster 'foo' is ready" or a similar
    # success marker — Agent P chooses the renderer copy.
    assert any(
        token in combined for token in ("ready", "ensured", "created", "ok")
    )
    assert "foo" in result.stdout + result.stderr


def test_cluster_status_json(
    cli_runner: CliRunner, patched_kind_runtime: FakeClusterRuntime
) -> None:
    """With ``--log-format=json`` the status output is JSON-shaped."""
    # Make sure the cluster is known to the fake runtime first.
    patched_kind_runtime.create_cluster("foo", config=None)  # type: ignore[arg-type]

    result = cli_runner.invoke(
        main, ["--log-format=json", "cluster", "status", "foo"]
    )
    assert result.exit_code == 0, result.stderr or result.stdout

    # Parse the last JSON object on stdout — most renderers emit a final
    # status payload, possibly preceded by other event lines.
    candidate_lines = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]
    parsed: list[dict] = []
    for line in candidate_lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            parsed.append(obj)

    assert parsed, (
        f"no JSON object in status stdout: {result.stdout!r}"
    )
    # Some object should mention the cluster name.
    serialised = json.dumps(parsed)
    assert "foo" in serialised


def test_cluster_teardown_succeeds(
    cli_runner: CliRunner, patched_kind_runtime: FakeClusterRuntime
) -> None:
    patched_kind_runtime.create_cluster("foo", config=None)  # type: ignore[arg-type]
    result = cli_runner.invoke(main, ["cluster", "teardown", "foo"])
    assert result.exit_code == 0, result.stderr or result.stdout
    # The fake should have observed a delete_cluster call.
    operations = [op for op, _ in patched_kind_runtime.calls]
    assert "delete_cluster" in operations, (
        f"teardown didn't call delete_cluster; recorded: {operations!r}"
    )
