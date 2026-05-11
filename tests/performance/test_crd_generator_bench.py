"""Micro-benchmarks for :class:`CrdYamlGenerator`.

The CRD generator dominates the per-run YAML serialisation cost (the
structural schema is the largest document we emit). Budget is 100 ms
per call across the eight canonical scenarios.
"""

from __future__ import annotations

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import CodegenRequest, OpenAPIDocument
from ai_platform_generator.domain.generation.generators.crd import CrdYamlGenerator

#: Per-call mean budget, in seconds.
_MEAN_BUDGET_S: float = 0.10

_SCENARIOS = DemoCatalog().scenarios
_SCENARIO_IDS = [s.name for s in _SCENARIOS]


@pytest.mark.benchmark
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_SCENARIO_IDS)
def test_crd_generator_per_scenario(scenario, benchmark, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Bench :meth:`CrdYamlGenerator.generate` on each canonical scenario.

    The IR is built outside the timed section so we measure only the
    CRD generator (planning + sort + YAML dump). ``tmp_path`` is reused
    across iterations — the generator is purely functional with respect
    to the target directory (it never reads existing contents).
    """
    request = CodegenRequest.from_dict(scenario.request)
    ir: OpenAPIDocument = OpenAPIDocument.from_request(request)
    generator = CrdYamlGenerator()

    result = benchmark(generator.generate, ir, tmp_path)

    assert result, f"CrdYamlGenerator emitted no artefacts for {scenario.name}"
    mean = benchmark.stats["mean"]
    assert mean < _MEAN_BUDGET_S, (
        f"CrdYamlGenerator.generate({scenario.name}) mean={mean:.4f}s exceeds "
        f"budget {_MEAN_BUDGET_S:.3f}s"
    )
