"""Fixtures for the end-to-end suite.

These tests drive the canonical ``run.sh`` entrypoint and the
``ai-platform-generator`` CLI in real subprocesses, against a real
``kind`` cluster when one can be spun up. They are intentionally
*disabled by default* — the suite is gated behind the ``e2e`` marker
*and* skipped in :func:`pytest_collection_modifyitems` if the host
lacks ``kind``/``docker``.

The ``clean_cluster`` fixture creates and tears down the
``ai-platform-demo`` kind cluster via the production
:class:`KindClusterRuntime` adapter so we exercise the same code path
the application uses at runtime.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_SH = REPO_ROOT / "run.sh"
CLUSTER_NAME = "ai-platform-demo"


# Prototype workflow file retained for reference but not yet ported to the
# new architecture (see ``docs/ddd/08-implementation-roadmap.md``). It
# imports a top-level ``main`` module that no longer exists, so we omit it
# from collection here. Once the prototype is removed this list can shrink.
collect_ignore = ["test_complete_workflow.py"]


# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register e2e-suite-local markers so ``--strict-markers`` is happy.

    The repository's ``pyproject.toml`` already registers ``e2e``; the
    ``e2e_no_cluster`` opt-out is a suite-private marker we register
    here rather than in :mod:`pyproject` (Agent T's territory).
    """
    config.addinivalue_line(
        "markers",
        "e2e_no_cluster: e2e test that does not require kind+docker",
    )


# ---------------------------------------------------------------------------
# Marker / skip plumbing
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip the entire e2e suite when ``kind`` or ``docker`` are absent.

    We do this here (rather than per-test) so the developer-facing
    output is a single, obvious skip reason rather than a row per test.
    """
    del config  # unused
    skip_reason: str | None = None
    if shutil.which("kind") is None:
        skip_reason = "kind not on PATH"
    elif shutil.which("docker") is None:
        skip_reason = "docker not on PATH"
    if skip_reason is None:
        return
    skip_marker = pytest.mark.skip(reason=skip_reason)
    for item in items:
        if "e2e" in item.keywords:
            # Tests that explicitly opt out of the kind/docker requirement
            # (subprocess-only smoke tests) are tagged ``e2e_no_cluster``.
            if "e2e_no_cluster" in item.keywords:
                continue
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Path & env fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path of the repository root."""
    return REPO_ROOT


@pytest.fixture
def run_sh() -> Path:
    """Return the path to the canonical ``run.sh`` entrypoint."""
    return RUN_SH


@pytest.fixture
def tmp_output_dir(tmp_path: pytest.TempPathFactory) -> Path:
    """Per-test output directory, isolated from ``./generated_specs``.

    Tests pass this to the CLI via ``--output-dir`` so artefacts never
    spill into the repo working tree.
    """
    out = Path(tmp_path) / "generated_specs" / "postgrescluster"  # type: ignore[arg-type]
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def clean_kubeconfig(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Save and restore the ``KUBECONFIG`` env var.

    Tests that mutate ``KUBECONFIG`` (e.g. by pointing kind at a tmp
    file) must request this fixture so a leak does not affect later
    tests. The restoration happens at fixture teardown.
    """
    original = os.environ.get("KUBECONFIG")
    yield
    if original is None:
        monkeypatch.delenv("KUBECONFIG", raising=False)
    else:
        monkeypatch.setenv("KUBECONFIG", original)


# ---------------------------------------------------------------------------
# Tooling fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kind_available() -> None:
    """Skip the requesting test if ``kind`` is not on PATH."""
    if shutil.which("kind") is None:
        pytest.skip("kind not on PATH")
    if shutil.which("docker") is None:
        pytest.skip("docker not on PATH")


# ---------------------------------------------------------------------------
# Cluster fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_cluster(kind_available: None) -> Iterator[Any]:
    """Create the ``ai-platform-demo`` kind cluster, yield, then delete.

    Uses the production :class:`KindClusterRuntime` so the test
    exercises the same code path as ``run.sh`` and the CLI. The
    fixture is *function-scoped* on purpose — e2e tests are slow and
    we want each one to start from a clean slate. Promote to
    ``module`` scope locally if you need to chain.
    """
    del kind_available  # presence-only fixture
    from ai_platform_generator.adapters.runtime.kind import (
        KindClusterRuntime,
        default_cluster_config,
    )

    runtime = KindClusterRuntime()
    config = default_cluster_config(CLUSTER_NAME)
    cluster = runtime.create_cluster(CLUSTER_NAME, config)
    try:
        yield cluster
    finally:
        # Best-effort teardown — never fail the test on cleanup.
        try:
            runtime.delete_cluster(CLUSTER_NAME)
        except Exception:  # pragma: no cover - cleanup-only
            pass
