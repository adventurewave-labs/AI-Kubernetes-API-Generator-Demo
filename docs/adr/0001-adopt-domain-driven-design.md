# ADR-0001: Adopt Domain-Driven Design as the modelling discipline

## Status

Accepted — 2025-05-09

## Context

The AI Kubernetes API Generator straddles three very different worlds —
**natural-language understanding**, **Kubernetes API modelling**, and
**developer tooling**. Each world brings its own vocabulary
(*prompt / completion*, *kind / group / version*, *CLI option / TUI panel*) and
its own rate of change. Without an explicit modelling discipline these
vocabularies leak into each other, producing the classic anaemic-domain
symptoms: "god" classes, mixed concerns, and an inability to reason about
where new behaviour belongs.

The project also has multiple *integration partners* — LLM providers
(OpenRouter, OpenAI), `kubectl`, `kind`, the filesystem, terminal renderers —
each of which is liable to fail or change. We need a clear way to keep the
core domain insulated from those changes.

## Decision

We adopt **Domain-Driven Design (DDD)** as the primary modelling discipline.
Concretely:

1. The system is decomposed into explicit **bounded contexts** (see
   `docs/ddd/03-strategic-design.md` and `docs/ddd/bounded-contexts/`).
2. A **ubiquitous language** is captured in
   `docs/ddd/02-ubiquitous-language.md` and used in code, tests, log lines,
   commit messages, and documentation.
3. Each bounded context exposes its functionality through **application
   services** that orchestrate **aggregates**, **entities**, **value
   objects**, **domain events**, and **domain services** (see
   `docs/ddd/04-tactical-design.md`).
4. Integrations with external systems are mediated by **anti-corruption
   layers** (see `docs/ddd/07-anti-corruption-layers.md`).

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Layered/MVC only | Familiar, low ceremony | Does not produce a shared language; couples concerns across layers |
| Hexagonal architecture without DDD | Cleanly isolates IO | Solves only the integration problem, not the modelling problem |
| Clean architecture | Strong dependency rules | Often degenerates into "use-case classes" without a shared language |
| No explicit discipline | Fastest to start | Already producing duplication and naming drift in the prototype |

Note: Hexagonal layering is **complementary** to DDD and is adopted in
[ADR-0014](0014-hexagonal-ports-and-adapters.md). DDD answers
*what we are modelling*; hexagonal answers *how we structure dependencies*.

## Consequences

### Positive
- A single vocabulary across product, code, and docs.
- Clear ownership: every concept lives in exactly one context.
- Test boundaries fall out naturally (one suite per context).
- Onboarding becomes a matter of reading `docs/ddd/`.

### Negative / Trade-offs
- Up-front cost: identifying contexts and aggregates takes real effort.
- Risk of over-modelling small contexts.
- Requires discipline in code review to keep the language honest.

### Neutral
- The existing prototype must be refactored to match the model. This is staged
  in the implementation roadmap (`docs/ddd/08-implementation-roadmap.md`).

## Related Decisions

- ADR-0010: Multi-agent layered architecture with explicit bounded contexts
- ADR-0014: Hexagonal (ports and adapters) layering
- DDD: `docs/ddd/01-domain-vision.md`, `docs/ddd/03-strategic-design.md`
