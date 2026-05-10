# AI Kubernetes API Generator — Architecture & Design Documentation

This directory contains the formal architecture and design documentation for the
**AI Kubernetes API Generator**. It is organised around two complementary
disciplines:

1. **Architecture Decision Records (ADR)** — a chronological log of the
   significant technical, structural, and operational decisions that shape the
   system, written in the
   [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
2. **Domain-Driven Design (DDD)** — strategic and tactical models that describe
   the *problem space*, the *bounded contexts* into which the solution is
   carved, the *ubiquitous language* used inside each context, and the
   tactical patterns (aggregates, entities, value objects, domain services,
   repositories, and domain events) that implement them.

Together these documents are sufficient to **drive a full implementation** of
the system without re-reading the source code: every architectural choice is
justified, every domain concept has a name, and every component has a
responsibility.

---

## Repository layout

```
docs/
├── README.md                          ← you are here
├── adr/                               ← Architecture Decision Records
│   ├── README.md                      ← ADR index, status board, process
│   ├── 0000-template.md               ← copy this to start a new ADR
│   ├── 0001-…  through 0020-…         ← individual decisions
├── ddd/                               ← Domain-Driven Design documentation
│   ├── README.md                      ← DDD overview, reading order
│   ├── 01-domain-vision.md            ← problem statement & domain narrative
│   ├── 02-ubiquitous-language.md      ← canonical glossary
│   ├── 03-strategic-design.md         ← subdomains & context map
│   ├── 04-tactical-design.md          ← aggregates, entities, value objects
│   ├── 05-domain-events.md            ← event catalogue & event storm
│   ├── 06-application-services.md     ← use cases & orchestrations
│   ├── 07-anti-corruption-layers.md   ← integrations with external systems
│   ├── 08-implementation-roadmap.md   ← how to build it, phase by phase
│   └── bounded-contexts/              ← one document per context
│       ├── 01-intent-interpretation.md
│       ├── 02-api-modelling.md
│       ├── 03-artifact-generation.md
│       ├── 04-cluster-provisioning.md
│       ├── 05-user-interaction.md
│       └── 06-observability.md
```

Mermaid diagrams are inlined in each document so they render natively on
GitHub; there is no separate `diagrams/` directory.

---

## How to read this documentation

| Audience                        | Recommended reading order                                                                                                                                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **New contributor**             | `README.md` → `ddd/01-domain-vision.md` → `ddd/03-strategic-design.md` → `ddd/02-ubiquitous-language.md` → `adr/README.md`                                                                                               |
| **Implementer of a new module** | `ddd/03-strategic-design.md` → relevant `bounded-contexts/*.md` → `ddd/04-tactical-design.md` → relevant ADRs                                                                                                            |
| **Reviewer / architect**        | `adr/README.md` (status board) → individual ADRs → `ddd/03-strategic-design.md` → `ddd/07-anti-corruption-layers.md`                                                                                                     |
| **Operator / SRE**              | `adr/0006-kind-for-local-cluster-testing.md`, `adr/0012-api-key-and-secret-management.md`, `adr/0013-filesystem-as-artifact-store.md`, `adr/0017-observability-and-telemetry.md`, `bounded-contexts/06-observability.md` |
| **Product / stakeholder**       | `ddd/01-domain-vision.md` → `ddd/08-implementation-roadmap.md`                                                                                                                                                           |

---

## Document conventions

- All diagrams use **Mermaid** so they render directly on GitHub.
- ADRs are **immutable**: once accepted, a decision is superseded rather than
  edited. The `Status` field links to the superseding ADR.
- DDD documents reference ADRs by number (e.g. *see ADR-0004*) and vice-versa,
  so the two corpora stay synchronised.
- Code examples are illustrative; the canonical implementation lives under
  `src/ai_platform_generator/`.

---

## Maintaining the documentation

1. Any pull request that changes architectural intent **must** add or update an
   ADR. Use `adr/0000-template.md` as the starting point.
2. Any pull request that introduces a new domain concept **must** update
   `ddd/02-ubiquitous-language.md` and, if appropriate, the relevant
   bounded-context document.
3. Reviewers should reject changes that contradict an *Accepted* ADR without
   first proposing a *Superseding* ADR.
