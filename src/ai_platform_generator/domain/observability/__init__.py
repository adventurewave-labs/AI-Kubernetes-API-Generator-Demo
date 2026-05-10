"""Cross-cutting observability domain helpers.

These are domain-level building blocks (no I/O, no third-party SDKs)
shared by every adapter that produces logs / metrics / traces:

* :class:`SecretRedactor` + :class:`RedactionPolicy` — apply the rules
  from ``docs/ddd/bounded-contexts/06-observability.md`` section 9 and
  ADR-0017 / ADR-0020 to any payload before it leaves the process.
* :class:`MetricsRecorder` + :class:`MetricRecord` — translate domain
  events into the metric catalogue from
  ``docs/ddd/bounded-contexts/06-observability.md`` section 7.
* :class:`SpanCorrelator` — track the active span stack per ``run_id``
  so that an OTEL-shaped sink can map ``Stage*`` events to spans.

The module is deliberately framework-free: nothing here imports
``structlog`` or ``opentelemetry``. Adapters in
``adapters/telemetry/`` are the *only* place those SDKs are touched.
"""

from __future__ import annotations

from ai_platform_generator.domain.observability.metrics import (
    MetricRecord,
    MetricsRecorder,
)
from ai_platform_generator.domain.observability.redaction import (
    RedactionPolicy,
    SecretRedactor,
)
from ai_platform_generator.domain.observability.span_correlator import SpanCorrelator

__version__ = "0.1.0"

__all__ = [
    "MetricRecord",
    "MetricsRecorder",
    "RedactionPolicy",
    "SecretRedactor",
    "SpanCorrelator",
    "__version__",
]
