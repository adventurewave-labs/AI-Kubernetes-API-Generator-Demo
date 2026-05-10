# ADR-0010: Multi-agent layered architecture with explicit bounded contexts

## Status

Accepted — 2025-05-09

## Context

The prototype already exhibits three responsibilities tangled into a single
`PlatformExtensionAgent` class: prompt construction, network I/O,
JSON-parsing, validation, and request enhancement. As we add more
generators (Go controller, MCP server, GitOps overlays) and more validators
(security review, compliance checks), this class will grow without bound.

DDD ([ADR-0001](0001-adopt-domain-driven-design.md)) tells us *what* to
separate; we still need to choose *how* the separated contexts interact at
runtime.

## Decision

We adopt a **multi-agent layered architecture** with the following layers,
each populated by one or more *agents* (long-lived application services):

1. **Interaction Layer** (`User Interaction` context) — CLI / TUI / web
   adapters. Owns nothing but rendering and command parsing.
2. **Orchestration Layer** — a single `GenerationOrchestrator` application
   service that drives the end-to-end workflow.
3. **Domain Agents Layer** — one application service per bounded context:
   - `IntentInterpretationAgent` (LLM-driven NL → CodegenRequest).
   - `ApiModellingAgent` (CodegenRequest → OpenAPI IR).
   - `ArtifactGenerationAgent` (IR → CRD/YAML/Go).
   - `ClusterProvisioningAgent` (manifests → live cluster).
   - `ValidationAgent` (cross-cutting checks).
   - `ObservabilityAgent` (telemetry, audit).
4. **Adapter Layer** — concrete implementations of ports (LLM, FS,
   Kubernetes, telemetry sinks).

Communication between agents is via **typed application-service calls** and
**domain events** ([DDD `05-domain-events.md`](../ddd/05-domain-events.md)).
Agents do **not** share mutable state; each owns its own aggregates.

The orchestrator is a *Saga* in DDD terms: it sequences agents, listens for
their domain events, and either commits the workflow on success or runs
compensating actions on failure.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Single monolithic agent | Simplicity | The existing pain point — too many concerns in one place |
| Microservices over the network | Strong isolation | Vast operational overhead for a CLI tool |
| Pub/sub event bus only | Loose coupling | Hides flow; orchestration becomes implicit and hard to debug |
| Workflow engine (Temporal, Prefect) | Durable orchestration | Overkill for sub-second to single-minute workflows |

## Consequences

### Positive
- Each context is testable in isolation with a deterministic stub for its
  collaborators.
- New artefact generators slot in as additional `ArtifactGenerationAgent`
  strategies without touching upstream agents.
- Observability is uniform — every agent emits the same envelope of
  `started`, `progressed`, `succeeded`, `failed` events.

### Negative / Trade-offs
- Slightly more files and indirection than a flat layout.
- Orchestrator must be careful about partial failures; the explicit Saga
  pattern is documented in `docs/ddd/06-application-services.md`.

### Neutral
- The "multi-agent" label intentionally evokes both DDD application
  services and the AI-agent metaphor. Both fit; either reading is correct.

## Related Decisions

- ADR-0001: Adopt Domain-Driven Design as the modelling discipline
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0015: Template Method pattern for code generation
- ADR-0016: Validation pipeline with explicit error model
- DDD: `docs/ddd/03-strategic-design.md`,
  `docs/ddd/06-application-services.md`
