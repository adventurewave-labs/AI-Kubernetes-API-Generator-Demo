"""Micro-benchmarks for :class:`IRBuilder`.

The IR builder is the entry point to the API-Modelling bounded context
and is invoked once per generation run. Its budget is therefore
*tighter* than the downstream artefact generators: anything over 50 ms
per call is treated as a regression worth investigating.

The matrix iterates the eight canonical scenarios sourced from
:class:`DemoCatalog` (see ``conftest.benchmark_records``). Each scenario
is independently parametrised so the per-scenario figures can be
diffed against a saved baseline (``--benchmark-save=baseline``).
"""

from __future__ import annotations

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import CodegenRequest
from ai_platform_generator.domain.services.ir_builder import IRBuilder

#: Per-call mean budget, in seconds. Crossing this fails the test.
_MEAN_BUDGET_S: float = 0.05

_SCENARIOS = DemoCatalog().scenarios
_SCENARIO_IDS = [s.name for s in _SCENARIOS]


@pytest.mark.benchmark
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_SCENARIO_IDS)
def test_ir_builder_per_scenario(scenario, benchmark) -> None:  # type: ignore[no-untyped-def]
    """Bench :meth:`IRBuilder.build` on each canonical scenario.

    The fixture is constructed once outside the timed section so we
    measure the builder, not :meth:`CodegenRequest.from_dict`.
    """
    request = CodegenRequest.from_dict(scenario.request)
    builder = IRBuilder()

    result = benchmark(builder.build, request)

    assert result is not None
    mean = benchmark.stats["mean"]
    assert mean < _MEAN_BUDGET_S, (
        f"IRBuilder.build({scenario.name}) mean={mean:.4f}s exceeds budget "
        f"{_MEAN_BUDGET_S:.3f}s"
    )
