# ADR-0016: Validation pipeline with explicit error model

## Status

Accepted — 2025-05-09

## Context

Errors in this system arrive from many independent layers — the LLM
provider, JSON parsing, domain invariants, OpenAPI/CRD schema rules, the
filesystem, `kubectl`, `kind`, the user. The prototype currently raises
generic `ValueError` everywhere and matches on substring patterns of error
messages. That is brittle and hostile to the user.

We need:

- A stable **error taxonomy** that the CLI can render distinctively.
- A **validation pipeline** that reports *all* problems with an input, not
  just the first.
- A way for the orchestrator to decide which errors are recoverable
  (retry, fall back to demo mode) and which are terminal.

## Decision

We define a hierarchy of typed exceptions rooted at
`PlatformGeneratorError`:

```
PlatformGeneratorError
├── ConfigurationError
│   ├── MissingApiKey
│   ├── InvalidConfigFile
│   └── PrerequisiteMissing            (kubectl, kind, docker)
├── IntentInterpretationError
│   ├── LlmUnavailable                 (recoverable → demo mode)
│   ├── LlmAuthenticationFailed
│   ├── LlmRateLimited                 (recoverable → backoff)
│   ├── LlmResponseUnparseable
│   └── AmbiguousIntent
├── DomainValidationError              (carries list[FieldViolation])
│   ├── InvalidGroup
│   ├── InvalidVersion
│   ├── InvalidKind
│   ├── EmptySpec
│   └── UnsupportedSchema
├── ArtifactGenerationError
│   ├── TemplateRenderingError
│   ├── PostProcessingFailed           (gofmt, yamlfmt)
│   └── ChecksumMismatch
├── ClusterProvisioningError
│   ├── PrerequisiteMissing            (re-raised)
│   ├── ClusterCreationTimedOut
│   ├── KubectlInvocationFailed
│   └── ResourceVerificationFailed
└── PersistenceError
    ├── ArtifactWriteFailed
    └── ProvenanceCorrupted
```

Every error carries:

- `code`: a stable string (`E_INTENT_LLM_UNAVAILABLE`, `E_DOMAIN_INVALID_KIND`)
  used in telemetry and exit codes.
- `user_message`: human-friendly, actionable.
- `cause`: the originating exception, chained via `raise X from cause`.
- `recoverable`: bool — whether the orchestrator may retry or degrade.
- `field_violations` (for `DomainValidationError`): list of
  `FieldViolation(path, expected, actual, message)`.

The validation pipeline consists of explicit stages, each producing zero or
more `FieldViolation`s. Stages run *all* their checks even if earlier ones
failed, so the user sees a complete list of problems on a single attempt.

Stages:

1. **Syntactic** — JSON well-formed, required keys present.
2. **Lexical** — group/version/kind regex; CamelCase; reverse-DNS.
3. **Semantic** — at least one spec property; types are JSON-schema-legal;
   property names are valid Go / JSON identifiers.
4. **CRD-specific** — schema is structural; group is non-reserved; version
   uses Kubernetes-compatible alpha/beta naming.
5. **Cluster-specific** (only when cluster mode is selected) — name is
   valid DNS-1123; namespace exists.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Single `Exception` everywhere | Easiest | The existing pain point |
| Result/Either monad | Pure functional | Awkward in idiomatic Python, hurts traceback ergonomics |
| Pydantic validators only | Tight integration | No place for cross-field, cluster-aware, or lifecycle errors |
| Sentry-style structured exceptions only | Strong observability | Only useful at the edge; we still want types in the core |

## Consequences

### Positive
- The CLI can render errors with consistent styling and exit codes.
- The orchestrator's recovery logic is explicit and testable.
- Users see all their problems at once; they fix once and re-run.

### Negative / Trade-offs
- More boilerplate than `raise ValueError(...)`. Mitigated by helper
  factories.
- Public API contract: error classes and codes are part of the contract.
  Renaming is a breaking change.

### Neutral
- Error codes feed directly into [ADR-0017 telemetry](0017-observability-and-telemetry.md).

## Related Decisions

- ADR-0008: Pydantic and dataclasses for typed domain models
- ADR-0009: Graceful degradation to demo mode when AI is unavailable
- ADR-0017: Observability and telemetry strategy
- ADR-0019: Versioning, release, and packaging strategy
- DDD: `docs/ddd/04-tactical-design.md`,
  `docs/ddd/06-application-services.md`
