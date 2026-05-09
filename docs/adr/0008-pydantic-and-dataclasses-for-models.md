# ADR-0008: Pydantic and dataclasses for typed domain models

## Status

Accepted — 2025-05-09

## Context

Domain models cross three boundaries that historically corrupt invariants in
Python codebases:

1. **JSON in / JSON out** — LLM responses, OpenAPI documents, Kubernetes
   manifests.
2. **Persistence** — written to and read back from the filesystem
   ([ADR-0013](0013-filesystem-as-artifact-store.md)).
3. **Process boundaries** — passed to `kubectl`, rendered in the CLI,
   serialised in tests.

Each crossing is a chance for a `dict` to silently lose a field, gain an
extra one, or carry the wrong type. We need consistent validation at every
boundary without losing the ergonomics of dataclasses inside the domain
core.

## Decision

We adopt a two-tier typing strategy:

1. **Pydantic v2 `BaseModel`** for any object that crosses a process or
   persistence boundary. This includes:
   - `CodegenRequest` (parsed from LLM JSON).
   - `OpenAPIDocument` and the schemas it embeds.
   - `CrdManifest`, `InstanceManifest`.
   - All command-line options and config files.
2. **Plain `@dataclass(frozen=True)` value objects and entities** for
   in-process domain types where validation is enforced once at construction
   and never mutated afterwards. Value objects (e.g. `Group`, `Version`,
   `Kind`) are `frozen=True` and validated in `__post_init__`.

Aggregates expose Pydantic models at the boundary and dataclasses internally,
with explicit `from_pydantic` / `to_pydantic` adapters.

`mypy --strict` is enforced in CI. Pydantic's type checker plugin is
enabled.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Pydantic only | Single library | Heavy for in-process types; ties domain core to Pydantic |
| Dataclasses only | Standard library, lightweight | No serialization / validation story for boundaries |
| `attrs` | Mature, flexible | Largely overlaps with dataclasses; adds dependency without unique value |
| `msgspec` | Faster than Pydantic | Smaller ecosystem; less familiar to contributors |
| Bare dicts | Flexible | The exact failure mode this ADR exists to prevent |

## Consequences

### Positive
- Boundary validation is automatic: bad JSON is rejected with a typed error
  before it touches the domain.
- The domain core remains free of `BaseModel`, making it easy to test in
  isolation.
- IDE / static-analysis support is consistent.

### Negative / Trade-offs
- A single concept can have *two* representations (Pydantic + dataclass) and
  a translator. We accept this cost for clear layering.
- Pydantic v2's runtime overhead is non-trivial; we keep it at the edges
  rather than in hot loops.

### Neutral
- A migration from Pydantic v1 to v2 is captured here so the team does not
  relitigate it.

## Related Decisions

- ADR-0001: Adopt Domain-Driven Design as the modelling discipline
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0016: Validation pipeline with explicit error model
- DDD: `docs/ddd/04-tactical-design.md`
