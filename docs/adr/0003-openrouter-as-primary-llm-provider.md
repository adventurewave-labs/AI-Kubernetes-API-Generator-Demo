# ADR-0003: Use OpenRouter as the primary LLM provider with pluggable backends

## Status

Accepted — 2025-05-09

## Context

The Intent Interpretation bounded context (see
`docs/ddd/bounded-contexts/01-intent-interpretation.md`) needs an LLM to turn
natural-language descriptions into structured `CodegenRequest` objects.
Choosing a single provider couples us to that provider's pricing, latency,
availability, model catalogue, and content policy. At the same time,
abstracting too aggressively yields a "lowest common denominator" interface
that prevents us from exploiting provider-specific features (JSON mode,
structured output, prompt caching).

OpenRouter is attractive because:

- It exposes an OpenAI-compatible API surface (so the `openai` SDK works).
- It aggregates models across providers, including free tiers usable in CI
  and demos.
- It centralises billing and key management for downstream models.

## Decision

We use **OpenRouter** as the *default* LLM provider, accessed through the
official `openai` Python SDK pointed at OpenRouter's `/api/v1` base URL.

We additionally define a thin **`LlmProvider` port** (an interface in the
hexagonal sense, see [ADR-0014](0014-hexagonal-ports-and-adapters.md)) so
that:

1. Direct OpenAI / Anthropic / local Ollama backends can be added without
   touching domain code.
2. Tests can substitute a deterministic fake provider.
3. The Demo Mode fallback ([ADR-0009](0009-graceful-degradation-to-demo-mode.md))
   is just another implementation of the port.

The default model is configurable via the `OPENROUTER_MODEL` environment
variable; documented free-tier defaults are kept current in
`config/agent_config.yaml`.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| OpenAI direct | Most mature SDK | Single-vendor lock-in; no free tier for demos |
| Anthropic direct | High-quality models | Single-vendor lock-in; no JSON mode at the time of decision |
| Local LLM (Ollama / llama.cpp) only | No external dependency | Hardware requirements unsuitable for a demo tool |
| Multi-provider abstraction layer (LiteLLM, LangChain) | One adapter for many providers | Heavy dependency, opinionated abstractions that fight DDD modelling |

## Consequences

### Positive
- Free-tier-friendly out of the box.
- OpenAI SDK compatibility means familiar tooling.
- Provider portability: switching backends is an adapter change, not a domain
  change.

### Negative / Trade-offs
- An additional vendor in the trust chain.
- OpenRouter rate limits and quotas need to be surfaced as domain errors
  ([ADR-0016](0016-validation-pipeline-error-model.md)).
- Account-verification quirks (e.g. "user not found" when chat completions
  are restricted) must be detected and translated to actionable user messages.

### Neutral
- Provider-specific structured-output features (JSON mode) are exploited when
  available and degraded gracefully when not.

## Related Decisions

- ADR-0009: Graceful degradation to demo mode when AI is unavailable
- ADR-0012: Environment-variable-based API key and secret management
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0016: Validation pipeline with explicit error model
- DDD: `docs/ddd/bounded-contexts/01-intent-interpretation.md`
