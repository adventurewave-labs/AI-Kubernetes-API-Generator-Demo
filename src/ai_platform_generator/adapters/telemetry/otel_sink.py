"""OpenTelemetry-backed :class:`TelemetrySink` (opt-in).

The OTEL SDK is imported **lazily** so the library remains usable
(and CI / unit tests pass) without ``opentelemetry`` on the dependency
graph. Construction raises :class:`ConfigurationError` when the SDK is
not importable so callers can degrade gracefully — see ADR-0017.

When the env var ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, spans and
metrics are shipped to that endpoint via the OTLP exporter; otherwise
an in-memory exporter is wired up so tests can introspect what would
have been emitted.
"""

from __future__ import annotations

import contextlib
import importlib
import os
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.errors import ConfigurationError
from ai_platform_generator.domain.observability.metrics import MetricsRecorder
from ai_platform_generator.domain.observability.redaction import (
    RedactionPolicy,
    SecretRedactor,
)
from ai_platform_generator.domain.observability.span_correlator import SpanCorrelator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent
    from ai_platform_generator.ports.clock import Clock


# Wire-stable mapping from event name to span lifecycle action. Span
# *opens* are always paired with span *closes*; everything else lands
# as an annotation on the currently-active span.
_SPAN_OPEN_EVENTS: frozenset[str] = frozenset({"RunStarted", "StageStarted"})
_SPAN_CLOSE_EVENTS: frozenset[str] = frozenset(
    {"RunSucceeded", "RunFailed", "StageSucceeded", "StageFailed"},
)


class OtelSink:
    """Map :class:`DomainEvent`s to OpenTelemetry spans + meters.

    The constructor performs the SDK import; if that fails (e.g. the
    ``opentelemetry`` extras are not installed) it raises a
    :class:`ConfigurationError` with the exact message the docs
    promise — ``"opentelemetry not installed"``. Callers in the
    composition root catch this and substitute :class:`NoopSink`.
    """

    def __init__(
        self,
        *,
        service_name: str = "ai-platform-generator",
        clock: Clock | None = None,
        redactor: SecretRedactor | None = None,
    ) -> None:
        try:
            trace = importlib.import_module("opentelemetry.trace")
            metrics_api = importlib.import_module("opentelemetry.metrics")
            sdk_trace = importlib.import_module("opentelemetry.sdk.trace")
            sdk_trace_export = importlib.import_module("opentelemetry.sdk.trace.export")
            in_memory_exporter_mod = importlib.import_module(
                "opentelemetry.sdk.trace.export.in_memory_span_exporter",
            )
            sdk_resources = importlib.import_module("opentelemetry.sdk.resources")
            sdk_metrics = importlib.import_module("opentelemetry.sdk.metrics")
            sdk_metrics_export = importlib.import_module(
                "opentelemetry.sdk.metrics.export",
            )
        except ImportError as exc:
            raise ConfigurationError(
                "opentelemetry not installed",
                cause=exc,
            ) from exc

        self._trace_api: Any = trace
        self._metrics_api: Any = metrics_api
        self._service_name = service_name
        self._redactor = redactor or SecretRedactor(RedactionPolicy.default())
        self._span_correlator = SpanCorrelator()
        # The recorder needs a clock; if the caller didn't provide one
        # we fall back to a system clock (kept lazy so the test path
        # stays import-light).
        if clock is None:
            from ai_platform_generator.adapters.clock.system import SystemClock

            clock = SystemClock()
        self._metrics = MetricsRecorder(clock)

        resource = sdk_resources.Resource.create({"service.name": service_name})
        provider = sdk_trace.TracerProvider(resource=resource)

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:  # pragma: no cover - exercised in integration only
            otlp_exporter_mod = importlib.import_module(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter",
            )
            exporter = otlp_exporter_mod.OTLPSpanExporter(endpoint=endpoint)
            self._span_exporter = exporter
            provider.add_span_processor(sdk_trace_export.BatchSpanProcessor(exporter))
        else:
            in_memory_exporter = in_memory_exporter_mod.InMemorySpanExporter()
            self._span_exporter = in_memory_exporter
            provider.add_span_processor(
                sdk_trace_export.SimpleSpanProcessor(in_memory_exporter),
            )

        self._tracer_provider = provider
        self._tracer = provider.get_tracer(service_name)

        # Meter setup — also defaults to in-memory.
        reader = sdk_metrics_export.InMemoryMetricReader()
        meter_provider = sdk_metrics.MeterProvider(
            resource=resource,
            metric_readers=[reader],
        )
        self._metric_reader = reader
        self._meter_provider = meter_provider
        self._meter = meter_provider.get_meter(service_name)
        # Cache (otel-instrument) by name+kind; counters are rarely re-keyed.
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}

        # Active spans, keyed by span_id from :class:`SpanCorrelator`.
        # Used to call ``.end()`` on close and ``.add_event`` on
        # annotation events.
        self._spans: dict[str, Any] = {}
        # Context-management tokens returned by ``use_span`` so we can
        # detach in the right order.
        self._span_ctx: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # TelemetrySink protocol
    # ------------------------------------------------------------------

    def emit(self, event: DomainEvent) -> None:
        run_id = "" if event.run_id is None else str(event.run_id)
        attributes = self._attributes_for(event)

        if event.name in _SPAN_OPEN_EVENTS:
            span = self._tracer.start_span(name=event.name, attributes=attributes)
            span_id = self._span_correlator.open(run_id, event.name)
            self._spans[span_id] = span
        elif event.name in _SPAN_CLOSE_EVENTS:
            close_span_id = self._span_correlator.current(run_id)
            if close_span_id is not None:
                span_id = close_span_id
                span = self._spans.pop(span_id, None)
                if span is not None:
                    # Decorate with payload attributes before ending so
                    # backends that index span attributes can filter on
                    # outcome / duration.
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                    span.end()
                self._span_correlator.close(run_id, span_id)
        else:
            # Annotate the currently active span, if any.
            current_id = self._span_correlator.current(run_id)
            if current_id is not None:
                span = self._spans.get(current_id)
                if span is not None:
                    span.add_event(event.name, attributes=attributes)

        # Metric updates — drive OTEL meters via :class:`MetricsRecorder`.
        for record in self._metrics.from_event(event):
            self._update_meter(record)

    def flush(self) -> None:
        # Best-effort — sinks must never raise from ``flush``.
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            self._tracer_provider.force_flush()
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            self._meter_provider.force_flush()

    # ------------------------------------------------------------------
    # introspection helpers (used by tests)
    # ------------------------------------------------------------------

    @property
    def span_exporter(self) -> Any:
        return self._span_exporter

    @property
    def metric_reader(self) -> Any:
        return self._metric_reader

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _attributes_for(self, event: DomainEvent) -> dict[str, Any]:
        """Build OTEL-friendly attribute map from a redacted payload."""
        redacted = self._redactor.redact_mapping(
            {
                "event_id": str(event.event_id),
                "run_id": None if event.run_id is None else str(event.run_id),
                "context": event.context,
                "schema_version": event.schema_version,
                "payload": dict(event.payload),
            },
        )
        # OTEL attribute values must be primitives or homogeneous lists;
        # we flatten the payload one level and JSON-stringify nested
        # structures so the SDK doesn't reject them.
        flat: dict[str, Any] = {}
        for key, value in redacted.items():
            if key == "payload" and isinstance(value, dict):
                for pkey, pvalue in value.items():
                    flat[f"payload.{pkey}"] = _coerce_attribute(pvalue)
            else:
                flat[key] = _coerce_attribute(value)
        return flat

    def _update_meter(self, record: Any) -> None:
        """Record an observation against the OTEL meter for ``record``."""
        if record.kind == "counter":
            counter = self._counters.get(record.name)
            if counter is None:
                counter = self._meter.create_counter(record.name)
                self._counters[record.name] = counter
            counter.add(record.value, attributes=dict(record.labels))
        elif record.kind == "histogram":
            hist = self._histograms.get(record.name)
            if hist is None:
                hist = self._meter.create_histogram(record.name)
                self._histograms[record.name] = hist
            hist.record(record.value, attributes=dict(record.labels))
        elif record.kind == "gauge":  # pragma: no cover - none in catalogue today
            # OTEL's "gauge" is observable; for the synchronous path we
            # use an up-down counter as the closest equivalent.
            gauge = self._counters.get(record.name)
            if gauge is None:
                gauge = self._meter.create_up_down_counter(record.name)
                self._counters[record.name] = gauge
            gauge.add(record.value, attributes=dict(record.labels))


def _coerce_attribute(value: Any) -> Any:
    """Coerce an arbitrary Python value to an OTEL-friendly attribute."""
    if value is None:
        return ""
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)
