# Bounded Context — Observability

> **Purpose:** turn the stream of **Domain Events** into actionable
> telemetry — logs, metrics, traces, audit records — without leaking
> third-party SDKs into the domain.

This is a **supporting** subdomain. It is also the **shared kernel**
between every other context: the `DomainEvent` envelope and the error
taxonomy ([ADR-0016](../../adr/0016-validation-pipeline-error-model.md))
are defined here and consumed everywhere.

---

## 1. Responsibilities

1. Own the `DomainEvent` and `TelemetrySink` ports.
2. Translate every emitted event into:
   - a structured **log** line (always),
   - one or more **metric** updates (where applicable),
   - a **trace span** open/close or annotation (when OTEL is enabled).
3. Redact secrets before any payload leaves the process.
4. Surface tool / version / mode / git-sha as structured context on every
   record.
5. Provide an **audit trail** distinct from operational logs — the
   `ProvenanceManifest` that ships with every artefact bundle.

This context **does not**:

- Make any product decisions (no fallback logic, no validation).
- Touch user input (it sees only events).
- Persist domain aggregates (that is `RunRepository` /
  `ArtifactRepository`'s job).

## 2. Ubiquitous language

Originated here: **Domain Event**, **Telemetry Sink**, **Span**,
**Provenance**.

## 3. Aggregates and value objects

| Type                  | Pattern         | Notes                                                              |
| --------------------- | --------------- | ------------------------------------------------------------------ |
| `DomainEvent`         | Value object    | See [`../05-domain-events.md §2`](../05-domain-events.md#2-event-envelope). |
| `EventBus`            | Domain service  | Synchronous in-process publisher/subscriber.                        |
| `RedactionPolicy`     | Value object    | Patterns + custom regex list.                                       |
| `MetricRecord`        | Value object    | `(name, value, labels, timestamp)`.                                |

## 4. Domain services

| Service              | Responsibility                                                                            |
| -------------------- | ----------------------------------------------------------------------------------------- |
| `EventBus`           | In-process pub/sub. Synchronous, ordered per `run_id`.                                    |
| `EventDispatcher`    | Subscribes sinks; applies filters; ensures idempotent delivery.                           |
| `SecretRedactor`     | Redacts payloads against the `RedactionPolicy`.                                           |
| `MetricsRecorder`    | Translates events into `MetricRecord`s.                                                   |
| `SpanCorrelator`     | Maintains the active span stack per `run_id` for OTEL.                                    |
| `ErrorTranslator`    | Maps low-level exceptions to `PlatformGeneratorError` subclasses.                          |

## 5. Application service

`EventDispatcher` exposes:

```python
def publish(self, event: DomainEvent) -> None: ...
def subscribe(self, predicate: Callable[[DomainEvent], bool], sink: TelemetrySink) -> None: ...
def flush(self) -> None: ...
```

Domain code calls only `publish`. Subscriptions are wired in the
composition root ([`../06-application-services.md §7`](../06-application-services.md#7-composition-root)).

## 6. Sinks

(Detailed in [`../07-anti-corruption-layers.md §6`](../07-anti-corruption-layers.md#6-telemetrysink).)

The default in production: `MultiSink([StructlogSink, OtelSink?])`.
The default in tests: `RecordingSink`.

## 7. Metric catalogue

| Metric                                | Type      | Labels                                          | Source events                                                 |
| ------------------------------------- | --------- | ----------------------------------------------- | -------------------------------------------------------------- |
| `runs_total`                          | counter   | `outcome`                                       | `RunSucceeded` / `RunFailed`                                  |
| `run_duration_seconds`                | histogram | `outcome`                                       | `RunSucceeded` / `RunFailed`                                  |
| `stage_duration_seconds`              | histogram | `stage`, `outcome`                              | `StageSucceeded` / `StageFailed`                              |
| `llm_invocations_total`               | counter   | `provider`, `model`, `mode`, `outcome`          | `LlmInvocationSucceeded` / `LlmInvocationFailed`              |
| `llm_tokens_total`                    | counter   | `provider`, `model`, `direction`                | `LlmInvocationSucceeded`                                      |
| `demo_mode_engaged_total`             | counter   | `reason_code`                                   | `DemoModeEngaged`                                             |
| `artifact_generated_total`            | counter   | `artefact_type`                                 | `ArtifactGenerated`                                           |
| `cluster_creation_total`              | counter   | `runtime`, `outcome`                            | `ClusterCreationSucceeded` / `ClusterCreationFailed`          |
| `cluster_creation_duration_seconds`   | histogram | `runtime`, `outcome`                            | `ClusterCreationSucceeded` / `ClusterCreationFailed`          |
| `deployment_verifications_total`      | counter   | `outcome`                                       | `DeploymentVerified` / `DeploymentVerificationFailed`         |

These align with OpenTelemetry's metric semantic conventions where
applicable.

## 8. Span structure

```
run (root span)
├── stage:interpret
│   └── llm
├── stage:model
├── stage:generate
│   ├── artefact:openapi
│   ├── artefact:crd
│   └── artefact:instance
├── stage:provision
│   ├── cluster.create
│   ├── crd.apply
│   └── instance.apply
└── stage:verify
```

Each span carries common attributes: `run.id`, `tool.version`,
`tool.git_sha`, `provider.mode`. Span events correspond to non-span
domain events (e.g. `ArtifactRendered`).

## 9. Redaction policy

Default patterns scrubbed from every payload before leaving the process:

- `sk-[A-Za-z0-9]{20,}`     (OpenAI / generic API keys)
- `or-[A-Za-z0-9]{20,}`     (OpenRouter)
- `Bearer [A-Za-z0-9._-]+`  (HTTP bearer tokens)
- Anything tagged with `secret=true` in event metadata.
- Anything matching a user-configured custom regex
  (`AI_AGENT_REDACT_PATTERNS`).

The redactor runs **before** any sink sees the payload.

The full prompt and full response are **never** included in events by
default (per [ADR-0020](../../adr/0020-security-threat-model-and-hardening.md)).
Their hashes (SHA-256, salted) are included instead. Capture is enabled
explicitly with `--capture-prompts` and writes to a local-only file
unless a remote sink is also configured.

## 10. Audit / provenance

Operational telemetry is ephemeral by default. The **audit trail** lives
in `manifest.json` next to every artefact bundle and contains:

- Tool version + git SHA.
- Timestamp.
- Source `CodegenRequest` (with intent text *hash*, not the text itself,
  unless `--capture-prompts`).
- Provider, model, mode.
- File checksums.

Per [ADR-0019](../../adr/0019-versioning-release-and-packaging.md), this
is the basis for SLSA-style supply-chain attestation in future releases.

## 11. Domain events emitted

Observability is a *consumer* of domain events; it does not produce its
own. The closest thing it produces is **enriched** events (added
correlation IDs, redacted payloads) before re-emitting to sinks — but
those enrichments do not change the event identity.

## 12. Failure modes

| Failure                  | Outcome                                                                |
| ------------------------ | ---------------------------------------------------------------------- |
| Sink raises              | Catch & log to stderr (bootstrap logger); never propagate to the domain. |
| Redaction regex error    | Drop the offending field; emit the event with a warning attribute.      |
| OTEL exporter unreachable | Log once; OTEL SDK queues and drops oldest as it fills.                 |

The orchestrator never depends on observability for correctness. If
every sink fails, the run still succeeds.

## 13. Public contract

The `DomainEvent` envelope and the metric / span catalogues above are
the public contract of this context. All other contexts depend on them.

## 14. Testing strategy

- **Unit:** `EventBus`, `SecretRedactor`, `MetricsRecorder`, `ErrorTranslator`.
- **Integration:** `StructlogSink` rendering snapshots; `OtelSink` against
  an in-memory exporter.
- **Contract:** every domain event has at least one renderer and one
  metric / span mapping; verified by a generated test that walks
  `events/__init__.py`.

## 15. Future work

- Persistent run history (SQLite-backed `RunRepository`).
- Out-of-process telemetry collector for long-running TUI / web mode.
- Optional Prometheus exporter for the metric catalogue.
- SLSA Level 3 build provenance attestation in CI.
