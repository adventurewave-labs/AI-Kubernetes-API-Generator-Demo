# ADR-0018: Test pyramid: unit / integration / e2e / golden-file

## Status

Accepted — 2025-05-09

## Context

The system has multiple kinds of behaviour that need different validation
strategies:

- Pure domain logic (validation rules, schema mapping) — fast, deterministic.
- Adapter behaviour (LLM client, kubectl wrapper) — needs to talk to the
  external thing, but we cannot do that in CI for free.
- End-to-end demo flow — needs Docker + Kind + an LLM (real or fake).
- Generated artefacts — must be byte-stable across runs (or change in
  reviewable ways).

Without an explicit strategy, tests collapse into a single "everything-with-
mocks" tier that is slow, flaky, and gives weak guarantees.

## Decision

We adopt a four-tier test pyramid:

### 1. Unit tests (`tests/unit/`) — broad base

- Exercise domain models, value-object invariants, application services
  with fake adapters.
- No network, no filesystem (use `pytest`'s `tmp_path` only when essential),
  no subprocesses.
- Target latency: **< 50 ms per test**, < 30 s for the full suite.
- Coverage gate: **≥ 90 %** of `domain/` and `application/`.

### 2. Integration tests (`tests/integration/`)

- Exercise *one adapter at a time* against a real backend or a high-fidelity
  fake (e.g. `respx` for HTTP).
- LLM integration tests are gated behind `OPENROUTER_API_KEY` and a
  `--run-llm` pytest flag; they are **not** required in CI by default.
- Filesystem integration tests use `tmp_path`.
- Target latency: < 5 s per test.

### 3. End-to-end tests (`tests/e2e/`)

- Drive the CLI as a subprocess against a fresh Kind cluster.
- Run the full demo flow: parse → generate → deploy → verify.
- Gated behind `--run-e2e`; required in nightly CI, not in PR CI.
- Target latency: < 5 minutes for the full e2e suite.

### 4. Golden-file tests (`tests/golden/`)

- For every artefact generator, a curated set of `CodegenRequest` inputs
  produces a checked-in `expected/` directory of artefacts.
- Tests assert byte-equivalence after deterministic post-processing.
- A `--update-golden` flag rewrites the expectations; updates require human
  review of the diff in the PR.
- Cover at least: the eight scenarios listed in
  `docs/ddd/08-implementation-roadmap.md`.

### Cross-cutting

- All tiers run with `mypy --strict` and `ruff` clean.
- A flaky-test budget of zero: any test that fails non-deterministically is
  quarantined within 24 hours.
- Test data lives in `tests/fixtures/`; no test reaches into another test's
  fixtures.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Unit + e2e only | Simpler taxonomy | Loses adapter-level confidence; e2e becomes the only signal for many failures |
| Property-based testing for everything | Powerful | Useful in the unit tier but cannot replace integration / e2e |
| Snapshot tests via `syrupy` | Convenient | Fine for individual files; less explicit than golden-file directories with checked-in `expected/` |
| Manual QA only | Cheapest to start | Loses regression protection |

## Consequences

### Positive
- Clear ownership of which tier should catch which kind of bug.
- PR CI stays fast (unit + integration without LLM).
- Generated-artefact regressions become impossible to merge silently.

### Negative / Trade-offs
- Maintaining four tiers takes discipline.
- Golden updates can become noisy if templates change frequently — we
  invest in stable templates.

### Neutral
- The fake LLM adapter doubles as the demo-mode adapter
  ([ADR-0009](0009-graceful-degradation-to-demo-mode.md)).

## Related Decisions

- ADR-0009: Graceful degradation to demo mode when AI is unavailable
- ADR-0013: Filesystem as the artifact store for generated specs
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0015: Template Method pattern for code generation
- ADR-0016: Validation pipeline with explicit error model
