"""End-to-end benchmark for :class:`GenerationOrchestrator`.

Drives the full saga (interpret → model → generate) through the
all-fakes composition root (:func:`build_test_orchestrator`) so the
benchmark reflects orchestrator overhead + every stage's hot path,
without any real I/O or network.

The :class:`FakeLlmAdapter` wired by the test composition root is
queue-driven: each saga run dequeues exactly one canned response. We
re-enqueue the canonical ``postgres-cluster`` payload before every
benchmark iteration via the :meth:`benchmark.pedantic` setup hook so
the LLM never runs dry.

Budget: 1.0 s per call.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from ai_platform_generator.application.composition import build_test_orchestrator
from ai_platform_generator.application.orchestrator import GenerateParams

#: Per-call mean budget, in seconds.
_MEAN_BUDGET_S: float = 1.00

#: Canned LLM payload — shape mirrors Wave-0 prototype keys, which
#: :class:`IntentInterpretationService` knows how to legacy-parse. We
#: use a postgres-cluster-shaped intent so the matching scenario is
#: self-evident in the saved benchmark JSON.
_CANNED_LLM_RESPONSE: Mapping[str, Any] = {
    "group": "database.cnoe.io",
    "version": "v1alpha1",
    "kind": "PostgresCluster",
    "spec_properties": {
        "replicas": {"type": "integer"},
        "tlsEnabled": {"type": "boolean"},
        "storageGiB": {"type": "integer"},
    },
    "output_dir": "out/postgres-cluster",
    "description": (
        "A managed PostgreSQL cluster used by the Wave-6 perf benchmark."
    ),
}


@pytest.mark.benchmark
def test_full_saga_postgres_cluster(benchmark, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Bench :meth:`GenerationOrchestrator.run` end-to-end (no deploy)."""
    orchestrator = build_test_orchestrator()
    fake_llm = orchestrator._llm  # type: ignore[attr-defined]

    params = GenerateParams(
        intent_text="A managed PostgreSQL cluster with TLS and storage",
        deploy_to_cluster=False,
        output_dir=tmp_path,
        allow_demo_mode=False,
    )

    def _setup() -> tuple[tuple[Any, ...], dict[str, Any]]:
        # Re-prime the LLM queue before each timed iteration: the
        # FakeLlmAdapter pops the head response on every call.
        fake_llm.enqueue(dict(_CANNED_LLM_RESPONSE))
        return (params,), {}

    summary = benchmark.pedantic(
        orchestrator.run,
        setup=_setup,
        rounds=5,
        iterations=1,
        warmup_rounds=1,
    )

    assert summary is not None
    assert summary.state == "succeeded"
    mean = benchmark.stats["mean"]
    assert mean < _MEAN_BUDGET_S, (
        f"GenerationOrchestrator.run mean={mean:.4f}s exceeds budget "
        f"{_MEAN_BUDGET_S:.3f}s"
    )
