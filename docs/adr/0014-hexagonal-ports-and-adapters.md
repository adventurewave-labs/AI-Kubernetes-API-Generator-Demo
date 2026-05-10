# ADR-0014: Hexagonal (ports and adapters) layering

## Status

Accepted — 2025-05-09

## Context

DDD ([ADR-0001](0001-adopt-domain-driven-design.md)) tells us *what* to
model. The multi-agent decomposition
([ADR-0010](0010-multi-agent-layered-architecture.md)) tells us how those
models are arranged at runtime. We still need a rule for *which direction
dependencies are allowed to point* so that domain code never reaches into
infrastructure (LLM SDKs, `kubectl`, filesystem).

## Decision

We organise the codebase using the **Hexagonal (Ports & Adapters)** pattern,
also known as Clean Architecture. The dependency rule is:

> Domain code depends on **ports** (abstract interfaces). Adapters depend on
> ports and on the concrete external technology. **Nothing in the domain
> imports an adapter or any third-party SDK.**

Concrete layout:

```
src/ai_platform_generator/
├── domain/                  ← entities, value objects, aggregates, events
├── application/             ← agents (application services), sagas
├── ports/                   ← abstract interfaces:
│   ├── llm_provider.py
│   ├── artifact_repository.py
│   ├── cluster_runtime.py
│   ├── secret_provider.py
│   ├── telemetry_sink.py
│   └── clock.py
└── adapters/                ← concrete implementations:
    ├── llm/openrouter.py
    ├── llm/openai.py
    ├── llm/demo_mode.py     ← see ADR-0009
    ├── llm/fake.py          ← test double
    ├── repo/filesystem.py
    ├── runtime/kind.py
    ├── runtime/k3d.py
    ├── secrets/env.py
    ├── secrets/dotenv.py
    ├── telemetry/structlog.py
    ├── telemetry/otel.py
    └── cli/                 ← Click + Rich (see ADR-0007)
```

The `application/` layer wires ports to adapters at startup; the domain
core never sees a concrete class.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Layered (UI → Service → Repo → DB) | Familiar | Allows domain to import infrastructure types in practice |
| Onion architecture | Similar to hexagonal | Hexagonal terminology is closer to the team's vocabulary |
| Vertical slice / feature folders | Lean, modern | Works against the cross-cutting nature of bounded contexts |
| No layering | Fastest start | The exact failure mode this ADR prevents |

## Consequences

### Positive
- Domain code is unit-testable without LLMs, networks, or filesystems.
- Adapters can be swapped per environment (e.g. `kind` in dev,
  `kubectl` in prod) without changing domain code.
- Demo Mode ([ADR-0009](0009-graceful-degradation-to-demo-mode.md)) is just
  another adapter — no special branches in business logic.

### Negative / Trade-offs
- More files / more abstraction than the prototype.
- Wiring (composition root) needs explicit care — we centralise it in
  `application/composition.py` to keep it visible.

### Neutral
- This decision is *complementary* to DDD; the two are commonly conflated.
  Hexagonal is structural; DDD is conceptual.

## Related Decisions

- ADR-0001: Adopt Domain-Driven Design as the modelling discipline
- ADR-0009: Graceful degradation to demo mode when AI is unavailable
- ADR-0010: Multi-agent layered architecture with explicit bounded contexts
- DDD: `docs/ddd/03-strategic-design.md`,
  `docs/ddd/07-anti-corruption-layers.md`
