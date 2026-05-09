# ADR-0002: Use Python 3.10+ as the primary implementation language

## Status

Accepted — 2025-05-09

## Context

The system orchestrates LLM calls, manipulates JSON/YAML, validates schemas,
shells out to `kind` / `kubectl`, and renders a rich terminal UI. The
existing prototype is already written in Python and the surrounding
ecosystem (Pydantic, Click, Rich, `openai` SDK, `pyyaml`) is mature for these
exact responsibilities.

The artefacts the system *produces* (Go controllers, Kubernetes manifests)
are a separate concern — a generator does not need to be written in the same
language as the code it generates.

## Decision

We use **Python 3.10 or newer** as the primary implementation language for
the generator itself. Python 3.10 is the minimum because we rely on:

- Structural pattern matching (`match` / `case`) for parsing AI responses.
- `from __future__ import annotations` and PEP 604 (`X | Y`) union syntax.
- Improved type-hint ergonomics in standard library generics.

Generated artefacts (controllers, CRDs, sample instances) remain
language-appropriate (Go, YAML, JSON) per [ADR-0011](0011-go-controller-kubebuilder-scaffold.md)
and [ADR-0005](0005-kubernetes-crd-as-primary-output.md).

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Go | Same language as Kubernetes ecosystem; static typing | Weaker LLM/SDK story; slower iteration on prompt engineering |
| TypeScript / Node | Strong async story; rich CLI ecosystem | LLM SDKs less mature; YAML/Pydantic-equivalent ergonomics weaker |
| Rust | Performance, safety | Massive over-investment for a glue/orchestration tool |
| Polyglot (Python + Go) | Best of both | Doubles toolchain and packaging complexity for marginal gain |

## Consequences

### Positive
- Fast iteration on prompt engineering and AI orchestration.
- First-class libraries for every responsibility: Pydantic, Click, Rich,
  `pyyaml`, `openai`, `httpx`, `pytest`.
- Friendly to contributors from data-science and platform-engineering
  backgrounds.

### Negative / Trade-offs
- Slower at runtime than Go/Rust (mitigated: we are I/O-bound on LLM calls).
- Distribution/packaging requires a wheel or a container — see
  [ADR-0019](0019-versioning-release-and-packaging.md).
- No compile-time checks; we lean on `mypy --strict` and Pydantic to
  compensate.

### Neutral
- Generated Go code lives in a separate sub-tree and has its own toolchain.

## Related Decisions

- ADR-0008: Pydantic and dataclasses for typed domain models
- ADR-0011: Generate Go controllers using the kubebuilder scaffold pattern
- ADR-0019: Versioning, release, and packaging strategy
