# ADR-0009: Graceful degradation to demo mode when AI is unavailable

## Status

Accepted — 2025-05-09

## Context

The system has a hard external dependency on an LLM provider (see
[ADR-0003](0003-openrouter-as-primary-llm-provider.md)) that can fail for
many independent reasons:

- Missing or invalid API key.
- Network unavailable (offline laptop, restrictive corporate proxy, CI).
- Provider outage or rate limiting.
- SSL / certificate trust issues (corporate MITM).
- Account restrictions (e.g. OpenRouter's "user not found" for unverified
  chat-completions access).

A demo tool that simply throws when any of these happens will lose users
forever in the first 30 seconds. We need a behaviour that lets people
*see what the tool does* without burning trust.

## Decision

We implement a **Demo Mode** that activates automatically whenever the
configured `LlmProvider` is unavailable. Demo Mode:

1. Is itself an implementation of the `LlmProvider` port — the rest of the
   system has no idea it is talking to a fake.
2. Returns a *deterministic* `CodegenRequest` chosen from a curated catalogue
   of demo scenarios (`PostgreSQLCluster`, `RedisCluster`, `VectorDB`,
   `Notebook`, etc.) keyed off keywords in the user's input.
3. **Always** announces itself in user-facing output ("⚠ Running in demo
   mode — no live AI was used"). Silent fallback would be a footgun.
4. Records the underlying real-error in telemetry
   ([ADR-0017](0017-observability-and-telemetry.md)) so the operator knows
   *why* the fallback happened.
5. Is **opt-out** with `--no-fallback` / `AI_AGENT_NO_FALLBACK=true` for CI
   pipelines that want to fail loudly.

The selection between live and demo mode is performed once at agent
construction time. Once demo mode is engaged the same provider is used for
the entire session (no flapping mid-flow).

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Hard fail with a helpful error | Honest, predictable | Breaks the "two-minute demo" promise |
| Cached previous responses | Faster | Cache invalidation problems; not generalisable |
| Local LLM auto-bootstrap | No network needed | Heavy install; outside the project's scope today |
| Silent fallback | Smoothest UX | Removes user agency; hides root causes |

## Consequences

### Positive
- The `./run.sh demo` flow always succeeds end-to-end, even offline.
- Sales / conference demos have a deterministic, repeatable script.
- Maps naturally onto the hexagonal layering — no special branches in
  domain code.

### Negative / Trade-offs
- The demo catalogue must be maintained and kept representative.
- Users unfamiliar with the warning could mistake demo output for real AI
  output. Mitigated by visual styling and a `Mode: demo` line in the
  generated artefact metadata.

### Neutral
- The same mechanism doubles as a deterministic *test fixture* (see
  [ADR-0018](0018-test-pyramid-strategy.md)).

## Related Decisions

- ADR-0003: Use OpenRouter as the primary LLM provider with pluggable backends
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0016: Validation pipeline with explicit error model
- ADR-0017: Observability and telemetry strategy
- ADR-0018: Test pyramid: unit / integration / e2e / golden-file
- DDD: `docs/ddd/bounded-contexts/01-intent-interpretation.md`
