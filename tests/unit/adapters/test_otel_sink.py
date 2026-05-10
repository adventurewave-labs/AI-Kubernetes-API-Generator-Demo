"""Tests for :class:`OtelSink`. Skipped when ``opentelemetry`` is absent."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.domain.errors import ConfigurationError
from ai_platform_generator.domain.events.envelope import DomainEvent

OTEL_INSTALLED = importlib.util.find_spec("opentelemetry") is not None

pytestmark = pytest.mark.skipif(
    not OTEL_INSTALLED, reason="opentelemetry not installed"
)


def _event(
    name: str,
    *,
    run_id: str | None = "run-1",
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    return DomainEvent(
        event_id=uuid4(),
        run_id=run_id,
        name=name,
        schema_version=1,
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        context="orchestrator",
        payload=payload or {},
    )


class TestImportFailure:
    def test_missing_opentelemetry_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force the lazy import inside __init__ to fail.
        import importlib

        original = importlib.import_module

        def fake_import(name: str, *a: Any, **kw: Any) -> Any:
            if name.startswith("opentelemetry"):
                raise ImportError("simulated absence")
            return original(name, *a, **kw)

        monkeypatch.setattr(importlib, "import_module", fake_import)

        from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink

        with pytest.raises(ConfigurationError, match="opentelemetry not installed"):
            OtelSink()


class TestSpanLifecycle:
    def test_run_started_opens_span_and_run_succeeded_closes(self) -> None:
        from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink

        sink = OtelSink(clock=FrozenClock())
        sink.emit(_event("RunStarted"))
        sink.emit(_event("RunSucceeded", payload={"duration_seconds": 1.5}))
        sink.flush()

        finished = sink.span_exporter.get_finished_spans()
        assert len(finished) == 1
        assert finished[0].name == "RunStarted"

    def test_nested_stage_span(self) -> None:
        from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink

        sink = OtelSink(clock=FrozenClock())
        sink.emit(_event("RunStarted"))
        sink.emit(_event("StageStarted", payload={"stage": "interpret"}))
        sink.emit(
            _event("StageSucceeded", payload={"stage": "interpret", "duration_seconds": 0.1}),
        )
        sink.emit(_event("RunSucceeded", payload={"duration_seconds": 1.0}))
        sink.flush()
        finished = sink.span_exporter.get_finished_spans()
        names = [s.name for s in finished]
        # Stage span ends before run span (LIFO).
        assert names.index("StageStarted") < names.index("RunStarted")

    def test_annotation_event_attached_to_active_span(self) -> None:
        from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink

        sink = OtelSink(clock=FrozenClock())
        sink.emit(_event("RunStarted"))
        sink.emit(_event("ArtifactRendered", payload={"artefact_type": "crd"}))
        sink.emit(_event("RunSucceeded", payload={"duration_seconds": 0.1}))
        sink.flush()
        finished = sink.span_exporter.get_finished_spans()
        assert len(finished) == 1
        events_on_span = [e.name for e in finished[0].events]
        assert "ArtifactRendered" in events_on_span


class TestMetrics:
    def test_metrics_emitted_for_run_succeeded(self) -> None:
        from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink

        sink = OtelSink(clock=FrozenClock())
        sink.emit(_event("RunStarted"))
        sink.emit(_event("RunSucceeded", payload={"duration_seconds": 2.0}))
        sink.flush()
        data = sink.metric_reader.get_metrics_data()
        assert data is not None
        # Find at least one metric named ``runs_total``.
        names: set[str] = set()
        for resource_metric in data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    names.add(metric.name)
        assert "runs_total" in names
