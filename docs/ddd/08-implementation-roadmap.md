# 08 — Implementation Roadmap

This document describes how to **build the AI Kubernetes API Generator
from the model**, phase by phase. It is the canonical execution plan
that ties every ADR and DDD document together.

The plan assumes a clean checkout: it can be followed start-to-finish
to reproduce the system, or used to refactor the existing prototype
incrementally.

---

## 1. Guiding principles

1. **Build inside-out.** Start with the domain core; add adapters
   only when the core needs them.
2. **Always green main.** Each phase ends with all tests passing.
3. **Deletion is progress.** Where the prototype already implements a
   responsibility, prefer rewriting it inside the new layout to porting
   it verbatim.
4. **Demo from day one.** The `./run.sh demo` flow (see
   [`01-domain-vision.md §"Domain narrative"`](01-domain-vision.md))
   must work at the end of every phase, even if some artefacts are
   placeholders.
5. **Document while coding.** Any decision not already captured in an
   ADR is captured in the same PR via a new ADR.

---

## 2. Phase 0 — Foundations (≈ 2 days)

**Goal:** project scaffolding that everything else builds on.

### Deliverables

- [ ] `pyproject.toml` declaring Python ≥ 3.10, Pydantic v2, Click,
      Rich, structlog, Jinja2, pytest, mypy, ruff.
- [ ] Repository tree per [ADR-0014 §"Concrete layout"](../adr/0014-hexagonal-ports-and-adapters.md):

  ```
  src/ai_platform_generator/
      domain/  application/  ports/  adapters/  prompts/  templates/
  tests/
      unit/ integration/ e2e/ golden/ fixtures/
  ```

- [ ] CI: `ruff`, `mypy --strict`, `pytest`, coverage gate.
- [ ] `Makefile` (or `task`) with `lint`, `test`, `test-golden`,
      `demo`, `clean`.
- [ ] `docs/` index pages (this work) committed.
- [ ] CODEOWNERS, CONTRIBUTING, ISSUE/PR templates referencing ADR/DDD
      conventions.

### ADRs touched

[ADR-0002](../adr/0002-python-as-primary-language.md),
[ADR-0008](../adr/0008-pydantic-and-dataclasses-for-models.md),
[ADR-0014](../adr/0014-hexagonal-ports-and-adapters.md),
[ADR-0018](../adr/0018-test-pyramid-strategy.md),
[ADR-0019](../adr/0019-versioning-release-and-packaging.md).

### Done when

- `make demo` exists and prints "not implemented" cleanly.
- `make test` passes against an empty test suite.

---

## 3. Phase 1 — Domain core (≈ 3 days)

**Goal:** value objects, aggregates, and domain services for the three
core contexts (Intent Interpretation, API Modelling, Artifact
Generation), without any IO.

### Deliverables

- [ ] Value objects: `Group`, `Version`, `Kind`, `GVK`, `SpecProperty`,
      `PropertyConstraints`, `OutputPath`, `Checksum`, `ProviderMode`,
      `RunId`, `Intent`.
- [ ] Aggregates: `CodegenRequest`, `OpenAPIDocument`, `ArtifactBundle`
      (with `ProvenanceManifest`).
- [ ] Domain services: `RequestValidator`, `RequestEnhancer`,
      `IRBuilder`, `StructuralSchemaValidator`, `ChecksumService`.
- [ ] Error taxonomy ([ADR-0016](../adr/0016-validation-pipeline-error-model.md))
      under `domain/errors/`.
- [ ] `DomainEvent` envelope and the full event catalogue under
      `domain/events/`.
- [ ] Unit tests for every invariant; coverage ≥ 90 % of `domain/`.

### ADRs touched

[ADR-0001](../adr/0001-adopt-domain-driven-design.md),
[ADR-0004](../adr/0004-openapi-3-as-intermediate-representation.md),
[ADR-0005](../adr/0005-kubernetes-crd-as-primary-output.md),
[ADR-0008](../adr/0008-pydantic-and-dataclasses-for-models.md),
[ADR-0016](../adr/0016-validation-pipeline-error-model.md).

### Done when

- The eight canonical scenarios listed in §10 below build a
  `CodegenRequest` and an `OpenAPIDocument` byte-stably under unit
  tests.

---

## 4. Phase 2 — Ports and fakes (≈ 1 day)

**Goal:** define every port and provide an in-memory / fake adapter
for each, so application services can be developed and tested without
real backends.

### Deliverables

- [ ] Ports under `ports/`: `LlmProvider`, `ArtifactRepository`,
      `ClusterRuntime`, `SecretProvider`, `TelemetrySink`, `Clock`,
      `RunRepository`.
- [ ] Fake adapters under `adapters/.../fake.py` for each port.
- [ ] `RecordingSink` for tests with `assert_events_in_order`.
- [ ] `FrozenClock` for deterministic timestamps.

### ADRs touched

[ADR-0014](../adr/0014-hexagonal-ports-and-adapters.md),
[ADR-0017](../adr/0017-observability-and-telemetry.md).

### Done when

- A unit test can instantiate any application service with only fakes
  and assert events.

---

## 5. Phase 3 — Application services + orchestrator (≈ 3 days)

**Goal:** the orchestration saga and the per-context application
services.

### Deliverables

- [ ] `IntentInterpretationService`, `ApiModellingService`,
      `ArtifactGenerationService`, `ClusterProvisioningService`.
- [ ] `GenerationOrchestrator` saga with stage decorator, recovery
      rules, compensating actions ([`06-application-services.md §4`](06-application-services.md#4-the-generation-orchestrator-saga)).
- [ ] `EventDispatcher` and its subscription wiring.
- [ ] `composition.py` with default wiring against fakes.
- [ ] Unit + integration tests for the orchestrator's recovery
      branches.

### ADRs touched

[ADR-0009](../adr/0009-graceful-degradation-to-demo-mode.md),
[ADR-0010](../adr/0010-multi-agent-layered-architecture.md),
[ADR-0016](../adr/0016-validation-pipeline-error-model.md).

### Done when

- A test exists for every recovery row in
  [`06-application-services.md §4.2`](06-application-services.md#42-recovery-rules).

---

## 6. Phase 4 — Real adapters (≈ 4 days)

**Goal:** replace fakes with real adapters, one port at a time.

### Deliverables (in this order)

1. [ ] **`FilesystemArtifactRepository`** with path-safety guards
       ([ADR-0013](../adr/0013-filesystem-as-artifact-store.md),
        [ADR-0020](../adr/0020-security-threat-model-and-hardening.md)).
2. [ ] **`StructlogSink`** with TTY/JSON renderers and redaction
       ([ADR-0017](../adr/0017-observability-and-telemetry.md)).
3. [ ] **`EnvSecretProvider` + `DotenvSecretProvider`** chain
       ([ADR-0012](../adr/0012-api-key-and-secret-management.md)).
4. [ ] **`OpenRouterLlmAdapter`** with full error translation
       ([ADR-0003](../adr/0003-openrouter-as-primary-llm-provider.md)).
5. [ ] **`OpenAiLlmAdapter`** as a pluggable secondary.
6. [ ] **`DemoModeLlmAdapter`** with curated catalogue
       ([ADR-0009](../adr/0009-graceful-degradation-to-demo-mode.md)).
7. [ ] **`KindClusterRuntime`** with subprocess hygiene
       ([ADR-0006](../adr/0006-kind-for-local-cluster-testing.md),
        [ADR-0020](../adr/0020-security-threat-model-and-hardening.md)).
8. [ ] **`OtelSink`** opt-in
       ([ADR-0017](../adr/0017-observability-and-telemetry.md)).

Each adapter ships with unit tests using fakes + at least one
integration test against the real backend (gated behind a flag).

### Done when

- The full live flow works against OpenRouter and Kind.
- Demo Mode works offline with `--no-fallback` correctly aborting.

---

## 7. Phase 5 — Generators (≈ 4 days)

**Goal:** ship the four default artefact generators and the Template
Method base class.

### Deliverables

1. [ ] `ArtifactGenerator` base + `ArtifactPlanner` + `Renderer`
       (Jinja2, `StrictUndefined`)
       ([ADR-0015](../adr/0015-template-method-for-code-generation.md)).
2. [ ] `OpenApiGenerator` (just serialises the IR).
3. [ ] `CrdYamlGenerator`.
4. [ ] `InstanceYamlGenerator`.
5. [ ] `GoControllerGenerator`
       ([ADR-0011](../adr/0011-go-controller-kubebuilder-scaffold.md)).
6. [ ] Idempotency verifier and a property test that random valid IRs
       round-trip byte-stably.
7. [ ] Golden tests for the eight scenarios.

### Done when

- Every scenario in §10 has a checked-in `expected/` directory and
  passes `make test-golden`.

---

## 8. Phase 6 — User Interaction (CLI) (≈ 2 days)

**Goal:** Click commands, Rich rendering, and stable exit codes.

### Deliverables

- [ ] `main` group + global options.
- [ ] Commands: `generate`, `interactive`, `build`, `examples`,
      `cluster ensure|teardown|status`, `validate`, `runs list|show`,
      `version`.
- [ ] `RichRenderer`, `JsonRenderer`, `QuietRenderer`.
- [ ] Exit-code mapping per
      [`bounded-contexts/05-user-interaction.md §7`](bounded-contexts/05-user-interaction.md#7-exit-codes).
- [ ] CLI snapshot tests under `tests/golden/cli/`.

### ADRs touched

[ADR-0007](../adr/0007-click-and-rich-for-cli.md).

### Done when

- `python -m ai_platform_generator.cli generate "..."` works against
  the real composition root, with both TTY and JSON output.

---

## 9. Phase 7 — End-to-end demo + packaging (≈ 2 days)

**Goal:** `./run.sh demo` works on a clean machine.

### Deliverables

- [ ] `run.sh demo` orchestrates: prerequisite install hint, secret
      check, `cluster ensure`, `generate`, `verify`, summary.
- [ ] PyPI-publishable package; container image build pipeline.
- [ ] Multi-arch container image with cosign signature
      ([ADR-0019](../adr/0019-versioning-release-and-packaging.md)).
- [ ] SBOM (CycloneDX) generation in CI
      ([ADR-0020](../adr/0020-security-threat-model-and-hardening.md)).
- [ ] Documented release process; `CHANGELOG.md` automated from
      Conventional Commits.

### Done when

- A fresh clone runs `./run.sh demo` to a deployed CRD in < 3 minutes
  on a warm Docker daemon.

---

## 10. Canonical scenarios

These are the **eight scenarios** that drive golden tests, demo-mode
catalogue, and product copy. They span the type space the system must
handle.

| # | Scenario             | Group                    | Kind             | Notable property types                                  |
| - | -------------------- | ------------------------ | ---------------- | ------------------------------------------------------- |
| 1 | PostgreSQL Cluster   | `database.cnoe.io`       | `PostgresCluster`| `replicas` (int 1-7), `tlsEnabled` (bool), `backupSchedule` (string with cron pattern) |
| 2 | Redis Cluster        | `cache.cnoe.io`          | `RedisCluster`   | `memoryGiB` (int), `port` (int 1-65535), `persistence` (bool) |
| 3 | Vector Database      | `ai.platform.cnoe.io`    | `VectorDB`       | `engineType` (enum), `replicas` (int 1-10), `dimensions` (int) |
| 4 | Notebook             | `datascience.cnoe.io`    | `Notebook`       | `cpu` (string), `memory` (string), `gpu` (bool)         |
| 5 | Database Backup      | `database.cnoe.io`       | `DatabaseBackup` | `schedule` (string), `retentionDays` (int), `enabled` (bool) |
| 6 | Cache Cluster (alias)| `platform.cnoe.io`       | `CacheCluster`   | `size` (string), `memory` (string), `port` (int)        |
| 7 | Monitoring Service   | `observability.cnoe.io`  | `MonitoringService` | `interval` (string), `targets` (array<string>), `alertEnabled` (bool) |
| 8 | ML Pipeline          | `ai.platform.cnoe.io`    | `MLPipeline`     | `stages` (array<string>), `parallelism` (int), `gpuEnabled` (bool) |

Every scenario must:

- Validate cleanly against the structural-schema rules.
- Round-trip through the IR byte-stably.
- Produce a CRD that `kubectl apply --dry-run=server` accepts on a
  fresh cluster (in CI).

---

## 11. Cross-cutting backlog (continuous)

These items are not phase-bound; they are addressed throughout.

- **Documentation**: keep ADRs current; add a new ADR for any
  architectural change in the same PR.
- **Telemetry**: every new event in `domain/events/` must have a
  renderer and (where relevant) a metric.
- **Security**: changes touching subprocess invocation, secrets, or
  generated code go through a security-review checklist
  ([ADR-0020](../adr/0020-security-threat-model-and-hardening.md)).
- **Test pyramid hygiene**: keep the unit / integration / e2e ratios
  per [ADR-0018](../adr/0018-test-pyramid-strategy.md).

---

## 12. Risk register

| Risk                                         | Mitigation                                                                                        |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| LLM provider API changes break adapters       | Adapter-only tests run nightly against live API; SDK pinned + Renovate-tracked.                   |
| Kubernetes structural-schema rules tighten    | Tests reapply CRDs against the latest stable Kubernetes version in CI; structural validator pinned. |
| Demo-mode catalogue drifts from real outputs  | Golden tests cover both live and demo paths; the same IR validator runs over demo outputs.        |
| Prompt-injection in user input                | Output never executed; structured-output validation; sanitisation; capped input length.           |
| Generated controller dependencies abandoned   | Pinned versions; Dependabot; quarterly maintenance ADR if a major dep moves.                       |

---

## 13. Definition of Done (whole system)

The project is "v1.0" when:

1. All eight canonical scenarios pass end-to-end against a real Kind
   cluster in CI.
2. Coverage ≥ 90 % across `domain/` and `application/`.
3. `mypy --strict` and `ruff` are green.
4. The PyPI package and signed container image are published.
5. A new contributor can run `./run.sh demo` from a clean clone to a
   deployed CRD in < 3 minutes.
6. Every architectural decision lives in an ADR; every domain concept
   lives in the ubiquitous-language glossary.

---

## 14. Beyond v1.0 (selected)

- TUI front-end sharing the Renderer Protocol.
- Web UI / REST API adapter.
- Multi-cluster deployments and conversion-webhook generation.
- Plug-in artefact generators discovered via Python entry points.
- SLSA Level 3 build-provenance attestation.
- Few-shot prompt assembly with explicit user-controlled history.
- "Bring your own LLM" via Ollama / local models as a default option.
