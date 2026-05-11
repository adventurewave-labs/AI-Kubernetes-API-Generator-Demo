"""Micro-benchmarks for :class:`ArtifactGenerationService`.

This benchmark wires the *whole* default generator set behind the
service (OpenAPI + CRD + Instance + Kustomization + MCP server +
Go controller, modulo whichever sibling agents have not yet landed).
The fakes used (:class:`InMemoryArtifactRepository`,
:class:`RecordingSink`, :class:`FrozenClock`) make the call non-IO and
deterministic, so the timing reflects pure CPU work.

Budget: 500 ms per call.
"""

from __future__ import annotations

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.adapters.repo.in_memory import (
    InMemoryArtifactRepository,
)
from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.application.services import ArtifactGenerationService
from ai_platform_generator.domain.aggregates import CodegenRequest, OpenAPIDocument
from ai_platform_generator.domain.generation.generators import default_generators
from ai_platform_generator.domain.values import RunId

#: Per-call mean budget, in seconds.
_MEAN_BUDGET_S: float = 0.50

_SCENARIOS = DemoCatalog().scenarios
_SCENARIO_IDS = [s.name for s in _SCENARIOS]


@pytest.mark.benchmark
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_SCENARIO_IDS)
def test_artifact_bundle_per_scenario(scenario, benchmark, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Bench :meth:`ArtifactGenerationService.run` on each canonical scenario.

    The IR and service composition live outside the timed section. Only
    the ``run(...)`` call (planning + N generators + manifest + persist)
    is measured.
    """
    request = CodegenRequest.from_dict(scenario.request)
    ir: OpenAPIDocument = OpenAPIDocument.from_request(request)

    service = ArtifactGenerationService(
        repo=InMemoryArtifactRepository(),
        events=RecordingSink(),
        clock=FrozenClock(),
        generators=list(default_generators()),
    )
    run_id = RunId.new()

    bundle = benchmark(
        service.run,
        ir,
        request=request,
        target_dir=tmp_path,
        run_id=run_id,
    )

    assert bundle is not None
    mean = benchmark.stats["mean"]
    assert mean < _MEAN_BUDGET_S, (
        f"ArtifactGenerationService.run({scenario.name}) mean={mean:.4f}s "
        f"exceeds budget {_MEAN_BUDGET_S:.3f}s"
    )
