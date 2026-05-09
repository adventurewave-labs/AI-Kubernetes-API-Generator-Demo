# ADR-0012: Environment-variable-based API key and secret management

## Status

Accepted — 2025-05-09

## Context

The system needs at minimum an LLM provider API key (`OPENROUTER_API_KEY`).
It may also need:

- An optional `OPENAI_API_KEY` for the secondary provider.
- Future credentials for Git providers (push generated repos), container
  registries (push controller images), or cloud Kubernetes clusters.

Secrets must never be:

- Committed to source control.
- Logged.
- Echoed to the terminal.
- Persisted to the filesystem in plaintext.

Different deployment modes (developer laptop, CI, container, Kubernetes job)
have different secret-providing mechanisms.

## Decision

Secrets are sourced through a single **`SecretProvider` port** with the
following adapter chain, evaluated in order:

1. **Process environment variables** (`os.environ`) — the canonical default.
2. **`.env` file** loaded via `python-dotenv` if present in the working
   directory and explicitly enabled with `--load-env`.
3. **`SecretProvider` plugins** (future): `keyring`, AWS Secrets Manager,
   HashiCorp Vault, Kubernetes Secret-projected files.

Specific guarantees:

- The CLI flag `--api-key` is supported but its value is **never** echoed
  back. It binds via Click's `envvar=` so the env var is the canonical
  surface.
- `.env.example` is committed; `.env` is `.gitignore`d.
- Logs redact any value that looks like a key (regex over `sk-…`,
  `or-…`, etc.) at the structured-logging layer
  ([ADR-0017](0017-observability-and-telemetry.md)).
- Errors that mention authentication failures show the **error class**, not
  the key value.
- Generated artefacts (CRDs, controllers, manifests) **must not** contain
  secret material. Where they reference secrets, they reference Kubernetes
  `Secret` objects by name.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Config file with secrets | Easier multi-secret setup | Encourages committing secrets |
| OS keyring only | Most secure on developer machines | Awkward in CI / containers |
| Vault required | Highest security | Operational overhead for a CLI tool |
| Hard-coded key | Worst, but obvious to consider and reject | Catastrophic |

## Consequences

### Positive
- Works identically on developer laptops, CI, containers, Kubernetes Jobs.
- Aligns with Twelve-Factor App configuration practices.
- Pluggable adapters mean future enterprise deployments can drop in Vault or
  AWS Secrets Manager without changing domain code.

### Negative / Trade-offs
- Users need to remember to `export` their key (mitigated by `.env`
  support).
- Per-shell secrets do not survive into systemd / launchd jobs without
  explicit configuration.

### Neutral
- The secret provider is a port; tests use a fake.

## Related Decisions

- ADR-0003: Use OpenRouter as the primary LLM provider with pluggable backends
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0017: Observability and telemetry strategy
- ADR-0020: Security threat model and hardening posture
- DDD: `docs/ddd/07-anti-corruption-layers.md`
