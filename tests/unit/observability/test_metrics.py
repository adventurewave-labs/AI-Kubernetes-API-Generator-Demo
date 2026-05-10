"""Tests for :mod:`ai_platform_generator.domain.observability.metrics`.

Each event type from ``docs/ddd/bounded-contexts/06-observability.md``
§7 must produce the metric(s) the catalogue prescribes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.domain.events.envelope import DomainEvent
from ai_platform_generator.domain.observability.metrics import (
    MetricRecord,
    MetricsRecorder,
)


def _event(name: str, *, payload: dict[str, object] | None = None) -> DomainEvent:
    """Build a synthetic envelope; the ``context`` is a valid stub."""
    context_for = {
        "RunSucceeded": "orchestrator",
        "RunFailed": "orchestrator",
        "StageSucceeded": "orchestrator",
        "StageFailed": "orchestrator",
        "LlmInvocationSucceeded": "intent",
        "LlmInvocationFailed": "intent",
        "DemoModeEngaged": "intent",
        "ArtifactGenerated": "generation",
        "ClusterCreationSucceeded": "cluster",
        "ClusterCreationFailed": "cluster",
        "DeploymentVerified": "cluster",
        "DeploymentVerificationFailed": "cluster",
    }
    return DomainEvent(
        event_id=uuid4(),
        run_id=None,
        name=name,
        schema_version=1,
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        context=context_for.get(name, "orchestrator"),
        payload=payload or {},
    )


@pytest.fixture
def recorder() -> MetricsRecorder:
    return MetricsRecorder(FrozenClock())


def names(records: tuple[MetricRecord, ...]) -> set[str]:
    return {r.name for r in records}


class TestRecord:
    def test_record_returns_value_object(self, recorder: MetricsRecorder) -> None:
        rec = recorder.record("foo", "counter", 1.0, {"a": "b"})
        assert rec.name == "foo"
        assert rec.kind == "counter"
        assert rec.value == 1.0
        assert dict(rec.labels) == {"a": "b"}

    def test_record_uses_clock(self) -> None:
        clock = FrozenClock()
        rec = MetricsRecorder(clock).record("foo", "counter", 1.0)
        assert rec.timestamp == clock.now()

    def test_record_default_labels_empty(self, recorder: MetricsRecorder) -> None:
        assert dict(recorder.record("foo", "counter", 1.0).labels) == {}


class TestEventToMetric:
    def test_run_succeeded(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("RunSucceeded", payload={"duration_seconds": 4.5}),
        )
        assert names(records) == {"runs_total", "run_duration_seconds"}
        runs_total = next(r for r in records if r.name == "runs_total")
        assert runs_total.kind == "counter"
        assert runs_total.value == 1.0
        assert runs_total.labels["outcome"] == "success"
        hist = next(r for r in records if r.name == "run_duration_seconds")
        assert hist.kind == "histogram"
        assert hist.value == 4.5

    def test_run_failed(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("RunFailed", payload={"duration_seconds": 1.0}),
        )
        outcomes = {r.labels["outcome"] for r in records}
        assert outcomes == {"failure"}

    def test_stage_succeeded(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event(
                "StageSucceeded",
                payload={"stage": "interpret", "duration_seconds": 0.25},
            ),
        )
        assert len(records) == 1
        rec = records[0]
        assert rec.name == "stage_duration_seconds"
        assert rec.labels == {"stage": "interpret", "outcome": "success"}
        assert rec.value == 0.25

    def test_stage_failed(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("StageFailed", payload={"stage": "generate"}),
        )
        assert records[0].labels["outcome"] == "failure"

    def test_llm_invocation_succeeded_with_tokens(
        self, recorder: MetricsRecorder
    ) -> None:
        records = recorder.from_event(
            _event(
                "LlmInvocationSucceeded",
                payload={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "mode": "live",
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                },
            ),
        )
        # Expect: invocation counter + 2 token counters.
        assert names(records) == {"llm_invocations_total", "llm_tokens_total"}
        token_records = [r for r in records if r.name == "llm_tokens_total"]
        directions = {r.labels["direction"] for r in token_records}
        assert directions == {"prompt", "completion"}
        prompt_tokens = next(
            r for r in token_records if r.labels["direction"] == "prompt"
        )
        assert prompt_tokens.value == 100.0

    def test_llm_invocation_succeeded_without_tokens(
        self, recorder: MetricsRecorder
    ) -> None:
        records = recorder.from_event(
            _event(
                "LlmInvocationSucceeded",
                payload={"provider": "openai", "model": "gpt-4o", "mode": "live"},
            ),
        )
        assert {r.name for r in records} == {"llm_invocations_total"}

    def test_llm_invocation_failed(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("LlmInvocationFailed", payload={"provider": "openai"}),
        )
        assert len(records) == 1
        assert records[0].name == "llm_invocations_total"
        assert records[0].labels["outcome"] == "failure"

    def test_demo_mode_engaged(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("DemoModeEngaged", payload={"reason_code": "no_api_key"}),
        )
        assert records[0].name == "demo_mode_engaged_total"
        assert records[0].labels == {"reason_code": "no_api_key"}

    def test_artifact_generated(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("ArtifactGenerated", payload={"artefact_type": "crd"}),
        )
        assert records[0].name == "artifact_generated_total"
        assert records[0].labels == {"artefact_type": "crd"}

    def test_cluster_creation_succeeded(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event(
                "ClusterCreationSucceeded",
                payload={"runtime": "kind", "duration_seconds": 30.0},
            ),
        )
        assert names(records) == {
            "cluster_creation_total",
            "cluster_creation_duration_seconds",
        }
        for r in records:
            assert r.labels == {"runtime": "kind", "outcome": "success"}

    def test_cluster_creation_failed(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(
            _event("ClusterCreationFailed", payload={"runtime": "kind"}),
        )
        for r in records:
            assert r.labels["outcome"] == "failure"

    def test_deployment_verified(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(_event("DeploymentVerified"))
        assert records[0].name == "deployment_verifications_total"
        assert records[0].labels == {"outcome": "success"}

    def test_deployment_verification_failed(self, recorder: MetricsRecorder) -> None:
        records = recorder.from_event(_event("DeploymentVerificationFailed"))
        assert records[0].labels == {"outcome": "failure"}

    def test_unknown_event_returns_empty(self, recorder: MetricsRecorder) -> None:
        assert recorder.from_event(_event("CommandStarted")) == ()
