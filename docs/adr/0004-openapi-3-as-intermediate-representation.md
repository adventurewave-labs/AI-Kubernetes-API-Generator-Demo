# ADR-0004: Adopt OpenAPI 3.0 as the canonical intermediate representation

## Status

Accepted — 2025-05-09

## Context

The system must produce multiple coordinated artefacts from a single user
intent: a Kubernetes CRD, a sample resource instance, optionally a Go
controller, and an HTTP-style API description for documentation tools. We
need a single source of truth that all of these generators consume, so that
the artefacts cannot diverge.

OpenAPI 3.0 is a widely adopted specification for describing JSON-shaped
APIs, and Kubernetes CRDs already use a *subset* of OpenAPI 3.0 schema for
their `openAPIV3Schema`. Standardising on OpenAPI gives us:

- A single schema language understood by humans and tools.
- Direct mapping from the `components.schemas` section into a CRD's
  `openAPIV3Schema`.
- Compatibility with downstream codegen tools (`openapi-mcp-codegen`,
  `oapi-codegen`, `openapi-generator`).

## Decision

The **canonical intermediate representation (IR)** of every generation run
is an OpenAPI 3.0 document. The pipeline is:

```
NaturalLanguageRequest → CodegenRequest → OpenAPI 3.0 document
                                            │
                                            ├── Kubernetes CRD YAML
                                            ├── Sample instance YAML
                                            ├── Go controller scaffold (optional)
                                            └── MCP server scaffold (optional)
```

All downstream artefact generators read from the OpenAPI document, never
from the raw `CodegenRequest`. This ensures:

1. The CRD's schema and the OpenAPI document's schema cannot drift.
2. Adding a new artefact generator means writing one consumer, not editing
   every existing one.
3. The IR is testable in isolation with golden-file tests
   ([ADR-0018](0018-test-pyramid-strategy.md)).

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| JSON Schema (no OpenAPI envelope) | Smaller, simpler | Loses metadata Kubernetes already expects in OpenAPI form |
| Protobuf | Strong typing, codegen support | No native CRD path; adds toolchain |
| Bespoke YAML schema | Total control | Reinvents OpenAPI badly; no ecosystem leverage |
| Direct CRD as IR | One fewer translation step | Locks us into Kubernetes only; harder to generate non-K8s artefacts |

## Consequences

### Positive
- Canonical, tool-friendly IR.
- Trivial mapping to CRD `openAPIV3Schema`.
- Free integration with documentation tools (Swagger UI, Redoc).

### Negative / Trade-offs
- Some Kubernetes-specific concerns (printer columns, additional printer
  columns, scale subresources) need extension fields (`x-kubernetes-*`)
  layered on top.
- Versioning of the IR itself becomes a concern — we pin to OpenAPI 3.0.x
  and treat 3.1 migration as a future ADR.

### Neutral
- The IR is materialised as JSON for tooling compatibility but rendered as
  YAML in user-facing artefacts.

## Related Decisions

- ADR-0005: Generate Kubernetes Custom Resource Definitions as primary output
- ADR-0011: Generate Go controllers using the kubebuilder scaffold pattern
- ADR-0015: Template Method pattern for code generation
- DDD: `docs/ddd/bounded-contexts/02-api-modelling.md`,
  `docs/ddd/bounded-contexts/03-artifact-generation.md`
