# Architecture Decision Records (ADR)

This directory holds the **Architecture Decision Records** for the AI
Kubernetes API Generator. Each ADR captures a single decision, the context
that produced it, the alternatives that were weighed, and the consequences
the team has agreed to live with.

We use the [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
extended with explicit *Alternatives Considered*, *Consequences*, and *Related
Decisions* sections to make causal links between ADRs explicit.

---

## ADR status board

| #    | Title                                                                            | Status   | Date       | Supersedes / Superseded by |
| ---- | -------------------------------------------------------------------------------- | -------- | ---------- | -------------------------- |
| 0001 | [Adopt Domain-Driven Design as the modelling discipline](0001-adopt-domain-driven-design.md) | Accepted | 2025-05-09 | —                          |
| 0002 | [Use Python 3.10+ as the primary implementation language](0002-python-as-primary-language.md) | Accepted | 2025-05-09 | —                          |
| 0003 | [Use OpenRouter as the primary LLM provider with pluggable backends](0003-openrouter-as-primary-llm-provider.md) | Accepted | 2025-05-09 | —                          |
| 0004 | [Adopt OpenAPI 3.0 as the canonical intermediate representation](0004-openapi-3-as-intermediate-representation.md) | Accepted | 2025-05-09 | —                          |
| 0005 | [Generate Kubernetes Custom Resource Definitions as primary output](0005-kubernetes-crd-as-primary-output.md) | Accepted | 2025-05-09 | —                          |
| 0006 | [Use Kind for local Kubernetes cluster testing](0006-kind-for-local-cluster-testing.md) | Accepted | 2025-05-09 | —                          |
| 0007 | [Use Click + Rich for the command-line interface](0007-click-and-rich-for-cli.md) | Accepted | 2025-05-09 | —                          |
| 0008 | [Pydantic and dataclasses for typed domain models](0008-pydantic-and-dataclasses-for-models.md) | Accepted | 2025-05-09 | —                          |
| 0009 | [Graceful degradation to demo mode when AI is unavailable](0009-graceful-degradation-to-demo-mode.md) | Accepted | 2025-05-09 | —                          |
| 0010 | [Multi-agent layered architecture with explicit bounded contexts](0010-multi-agent-layered-architecture.md) | Accepted | 2025-05-09 | —                          |
| 0011 | [Generate Go controllers using the kubebuilder scaffold pattern](0011-go-controller-kubebuilder-scaffold.md) | Accepted | 2025-05-09 | —                          |
| 0012 | [Environment-variable-based API key and secret management](0012-api-key-and-secret-management.md) | Accepted | 2025-05-09 | —                          |
| 0013 | [Filesystem as the artifact store for generated specs](0013-filesystem-as-artifact-store.md) | Accepted | 2025-05-09 | —                          |
| 0014 | [Hexagonal (ports and adapters) layering](0014-hexagonal-ports-and-adapters.md)  | Accepted | 2025-05-09 | —                          |
| 0015 | [Template Method pattern for code generation](0015-template-method-for-code-generation.md) | Accepted | 2025-05-09 | —                          |
| 0016 | [Validation pipeline with explicit error model](0016-validation-pipeline-error-model.md) | Accepted | 2025-05-09 | —                          |
| 0017 | [Observability and telemetry strategy](0017-observability-and-telemetry.md)      | Accepted | 2025-05-09 | —                          |
| 0018 | [Test pyramid: unit / integration / e2e / golden-file](0018-test-pyramid-strategy.md) | Accepted | 2025-05-09 | —                          |
| 0019 | [Versioning, release, and packaging strategy](0019-versioning-release-and-packaging.md) | Accepted | 2025-05-09 | —                          |
| 0020 | [Security threat model and hardening posture](0020-security-threat-model-and-hardening.md) | Accepted | 2025-05-09 | —                          |

---

## Statuses

- **Proposed** — under discussion, not yet binding.
- **Accepted** — the decision is in force; new code must comply.
- **Superseded by ADR-NNNN** — historical, replaced by a later decision.
- **Deprecated** — no longer in force but not replaced (rare).
- **Rejected** — explicitly considered and turned down. Kept for the record so
  the same idea is not relitigated without new information.

---

## Authoring a new ADR

1. Copy `0000-template.md` to `NNNN-short-title.md` where `NNNN` is the next
   available number.
2. Fill in **every** section. If a section is genuinely not applicable, write
   *"Not applicable — <reason>"* rather than deleting it.
3. Open a pull request. The PR description should link to the ADR and call out
   any ADR it supersedes.
4. Once merged, update the **ADR status board** above and any `Related
   Decisions` cross-references in adjacent ADRs.

## Anatomy of an ADR

```
# ADR-NNNN: <imperative-mood title>

## Status
<Proposed | Accepted | Superseded by ADR-XXXX | Deprecated | Rejected>

## Context
What forces are at play? What is the problem we are trying to solve?

## Decision
The choice we are making, in active voice and present tense.

## Alternatives Considered
Options we explicitly evaluated and why they were not chosen.

## Consequences
Positive, negative, and neutral consequences. What becomes easier? Harder?

## Related Decisions
Cross-references to other ADRs and DDD documents.
```
