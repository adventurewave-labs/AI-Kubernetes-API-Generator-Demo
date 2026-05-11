"""Pytest configuration for the performance / benchmark suite.

The suite uses :mod:`pytest-benchmark` (registered as a runtime
dependency in :file:`pyproject.toml` under ``[project.optional-dependencies] dev``).
For environments where the plugin is not yet installed the suite still
*collects* — the :func:`pytest.mark.benchmark` marker is a no-op when
the plugin is absent and tests that rely on the ``benchmark`` fixture
will simply be skipped at runtime via the ``pytestmark`` guard.

The ``benchmark_records`` fixture is the single source of truth for the
eight canonical scenarios (per
``docs/ddd/08-implementation-roadmap.md`` §10). It re-exposes the same
:class:`DemoScenario` records the golden tests consume via the
:class:`DemoCatalog`, so the perf and golden suites cannot drift.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

# The legacy ``test_codegen_performance.py`` file in this directory was
# authored against the Wave-0 prototype layout and imports modules that
# were removed in the DDD migration (`agent.agent_core`, `codegen.*`,
# `main`). It is excluded from collection here so the benchmark suite
# can be exercised via ``pytest tests/performance`` without the legacy
# import errors.
collect_ignore: list[str] = ["test_codegen_performance.py"]


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``benchmark`` marker even when the plugin is absent.

    ``pytest-benchmark`` registers its own marker once installed; doing
    it here as well is a no-op duplicate (pytest deduplicates by name)
    but ensures ``--strict-markers`` doesn't reject the marker when the
    plugin is not available.
    """
    config.addinivalue_line(
        "markers",
        "benchmark: micro-benchmark for the hot paths exercised by Wave-6 perf budgets",
    )


# ---------------------------------------------------------------------------
# Canonical scenarios fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def benchmark_records() -> Sequence[object]:
    """The eight canonical scenarios used across the perf suite.

    Sourced from :class:`DemoCatalog` so this stays in lock-step with
    the golden-test matrix. Each record is a
    :class:`~ai_platform_generator.adapters.llm.demo_catalog.DemoScenario`
    with a ``name``, ``keywords`` and a ``CodegenRequest.to_dict``-shaped
    ``request`` payload.
    """
    from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog

    return DemoCatalog().scenarios
