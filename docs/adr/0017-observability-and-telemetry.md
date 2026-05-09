# ADR-0017: Observability and telemetry strategy

## Status

Accepted — 2025-05-09

## Context

The system spans process boundaries (LLM HTTP calls, `kubectl` subprocesses,
`kind` lifecycle, filesystem writes). When something goes wrong the user
cares about *why*, and the maintainer cares about aggregate trends ("are
LLM 429s rising?", "is demo-mode fallback firing more often?").

We need a single observability story that:

- Works in `--quiet` (CI), default (developer), and `--debug` modes.
- Redacts secrets per [ADR-0012](0012-api-key-and-secret-management.md).
- Plays nicely with users' existing tooling (stdout JSON in CI, Rich-styled
  console for humans).
- Carries through to OpenTelemetry for users who want it, without making it
  mandatory.

## Decision

Three observability primitives:

1. **Structured logs** via `structlog` configured for two renderers:
   - **`KeyValueRenderer`** in TTY mode, colourised by Rich
     ([ADR-0007](0007-click-and-rich-for-cli.md)).
   - **`JSONRenderer`** in non-TTY / `--log-format=json` mode.
2. **Metrics** through an internal `MetricsRecorder` port that records:
   - `generation_duration_seconds` (histogram, by stage)
   - `llm_tokens_total` (counter, by provider, model, mode)
   - `llm_failures_total` (counter, by error code)
   - `artifact_generated_total` (counter, by artefact type)
   - `cluster_operations_total` (counter, by operation, outcome)
3. **Traces** via OpenTelemetry, opt-in by setting
   `OTEL_EXPORTER_OTLP_ENDPOINT`. When enabled, every application service
   wraps its operation in a span with semantic-convention attributes.

A **`TelemetrySink` port** with adapters:

- `StructlogSink` (default).
- `OtelSink` (opt-in).
- `NoopSink` (tests, `--quiet`).
- `MultiSink` (compose).

Domain code emits **domain events** ([DDD `05-domain-events.md`](../ddd/05-domain-events.md))
that the sink translates into log lines / metrics / spans. Domain code
never imports `structlog` or `opentelemetry` directly.

Redaction layer:

- A `SecretRedactor` runs over every log payload and span attribute.
- Pattern matches: `sk-…`, `or-…`, `Bearer …`, anything tagged
  `secret=true` in event metadata, anything matching a configured custom
  regex.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| `print` only | Zero dependency | No structure; cannot be parsed in CI |
| Standard `logging` | Built-in | Mutable global state; weak structured-log story |
| OTEL mandatory | Future-proof | Heavy; surprising for a CLI tool |
| Sentry-only | Great error tracking | Vendor lock-in; weak metrics/traces |

## Consequences

### Positive
- Same telemetry primitives whether you are debugging on a laptop or
  running in production CI.
- Demo-mode fallback rate is observable as a first-class metric.
- The OTEL adapter means generated controllers can be observed alongside
  the generator itself.

### Negative / Trade-offs
- Three primitives is more than two. We accept the cost for the explicit
  separation of concerns (events → logs/metrics/traces).
- OTEL dependency is heavy; we keep it optional.

### Neutral
- Telemetry is a port; tests use the noop adapter.

## Related Decisions

- ADR-0007: Use Click + Rich for the command-line interface
- ADR-0012: Environment-variable-based API key and secret management
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0016: Validation pipeline with explicit error model
- DDD: `docs/ddd/05-domain-events.md`,
  `docs/ddd/bounded-contexts/06-observability.md`
