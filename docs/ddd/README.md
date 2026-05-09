# Domain-Driven Design Documentation

This directory contains the Domain-Driven Design (DDD) documentation for the
**AI Kubernetes API Generator**. It complements the ADR documentation under
`docs/adr/`: ADRs describe *which* technical choices we have made and why;
DDD documents describe *what* we are modelling and how the model is
organised.

The decision to adopt DDD as our modelling discipline is captured in
[ADR-0001](../adr/0001-adopt-domain-driven-design.md).

---

## Reading order

| If you want to…                                                  | Read, in order…                                                                                                                                                                                |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Understand the product**                                       | [`01-domain-vision.md`](01-domain-vision.md) → [`03-strategic-design.md`](03-strategic-design.md)                                                                                              |
| **Speak the language correctly**                                 | [`02-ubiquitous-language.md`](02-ubiquitous-language.md)                                                                                                                                       |
| **Implement a new feature**                                      | [`03-strategic-design.md`](03-strategic-design.md) → relevant `bounded-contexts/*.md` → [`04-tactical-design.md`](04-tactical-design.md) → [`06-application-services.md`](06-application-services.md) |
| **Add an integration with an external system**                   | [`07-anti-corruption-layers.md`](07-anti-corruption-layers.md) → [`05-domain-events.md`](05-domain-events.md)                                                                                  |
| **Build the system from scratch**                                | [`08-implementation-roadmap.md`](08-implementation-roadmap.md)                                                                                                                                 |

---

## Documents

1. [**01 — Domain Vision**](01-domain-vision.md)
   Problem statement, target user, mission, and the narrative that frames
   the rest of the documentation.
2. [**02 — Ubiquitous Language**](02-ubiquitous-language.md)
   Canonical glossary. The terms here are used verbatim in code, tests,
   logs, commit messages, and product copy.
3. [**03 — Strategic Design**](03-strategic-design.md)
   Subdomain classification (core / supporting / generic), bounded contexts,
   context map, integration patterns, and team topologies.
4. [**04 — Tactical Design**](04-tactical-design.md)
   Aggregates, entities, value objects, domain services, repositories,
   factories, and invariants.
5. [**05 — Domain Events**](05-domain-events.md)
   Event catalogue, event-storming summary, and event-flow diagrams.
6. [**06 — Application Services**](06-application-services.md)
   Use cases, orchestration sagas, and the public surface of each bounded
   context.
7. [**07 — Anti-Corruption Layers**](07-anti-corruption-layers.md)
   How we integrate with LLM providers, Kubernetes, the filesystem, and
   downstream codegen tools without letting their models leak into our
   domain.
8. [**08 — Implementation Roadmap**](08-implementation-roadmap.md)
   Phase-by-phase plan to build the system in line with this model.

### Bounded contexts

Each context has a dedicated document under
[`bounded-contexts/`](bounded-contexts/):

1. [**Intent Interpretation**](bounded-contexts/01-intent-interpretation.md)
   Natural language → structured `CodegenRequest`.
2. [**API Modelling**](bounded-contexts/02-api-modelling.md)
   `CodegenRequest` → OpenAPI 3.0 IR.
3. [**Artifact Generation**](bounded-contexts/03-artifact-generation.md)
   IR → CRD, sample instance, Go controller, MCP server, …
4. [**Cluster Provisioning**](bounded-contexts/04-cluster-provisioning.md)
   Manifests → live Kubernetes cluster + verification.
5. [**User Interaction**](bounded-contexts/05-user-interaction.md)
   CLI / TUI / future web UI; rendering, prompts, progress.
6. [**Observability**](bounded-contexts/06-observability.md)
   Domain events → logs, metrics, traces, audit.

### Diagrams

All diagrams are inlined as Mermaid blocks inside the documents above so
they render natively on GitHub. There is no separate `diagrams/`
directory at this time.
