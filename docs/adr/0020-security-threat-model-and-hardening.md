# ADR-0020: Security threat model and hardening posture

## Status

Accepted — 2025-05-09

## Context

The system handles three kinds of sensitive material:

1. **LLM API keys** (developer secret).
2. **Cluster credentials** (kubeconfig, service-account tokens).
3. **Generated source code** that will run with cluster privileges
   (controllers).

It also accepts **untrusted natural-language input** that is forwarded to a
third-party LLM and returned as JSON. Any of those edges is a potential
attack surface.

We need a threat model that is shared by all contributors and a set of
hardening commitments that can be audited.

## Decision

### Threat model (STRIDE)

| Threat                 | Asset                  | Mitigation |
| ---------------------- | ---------------------- | ---------- |
| **Spoofing**           | LLM provider identity  | TLS, certificate pinning option, configurable trust roots |
| **Tampering**          | Generated artefacts    | SHA-256 digests in `manifest.json`; signed releases ([ADR-0019](0019-versioning-release-and-packaging.md)) |
| **Tampering**          | LLM responses          | JSON Schema validation; type-safe parsing; structured-output only |
| **Repudiation**        | Generation audit       | Provenance manifest with timestamp, user, model, mode |
| **Information disclosure** | API keys           | [ADR-0012](0012-api-key-and-secret-management.md); redacting log layer |
| **Information disclosure** | Prompts             | Configurable prompt-redaction; users can opt out of telemetry |
| **Denial of service**  | LLM rate limits        | Exponential backoff; demo-mode fallback |
| **Denial of service**  | Local resource exhaustion | Bounded subprocess timeouts; size caps on user input (default 8 KiB) |
| **Elevation of privilege** | Generated controllers | Distroless image, non-root UID `65532`, RBAC scoped to the CRD; documented review checklist |
| **Prompt injection**   | LLM behaviour          | System prompt isolation; structured-output enforcement; input sanitisation; never executing LLM output |
| **Supply chain**       | Dependencies           | Pinned hashes, Renovate/Dependabot, SBOM (CycloneDX), signed releases |

### Hardening commitments

1. **Input validation**
   - User input is sanitised (control characters stripped, length capped,
     UTF-8 normalised) before being passed to the LLM.
   - No LLM output is ever `exec`'d, `eval`'d, or rendered as a shell
     command. Output is parsed as JSON and validated against a schema.
2. **Subprocess hygiene**
   - All `kubectl` / `kind` / `docker` invocations use `subprocess.run`
     with `shell=False` and explicit argv lists.
   - Timeouts are mandatory.
   - Working directories are explicit; never relative.
3. **Filesystem hygiene**
   - Output paths are resolved with `Path.resolve()` and checked against
     the configured output root before any write (no path traversal).
   - File modes are explicit (`0o644` for artefacts, `0o600` for
     manifests containing host paths).
4. **Network hygiene**
   - TLS verification is **on** by default. The `--insecure-skip-tls-verify`
     flag exists for demo environments only; setting it logs a `WARN`
     event and is reflected in `manifest.json`.
   - HTTP timeouts are mandatory (default 30 s for connect, 60 s for read).
5. **Generated-artefact hardening**
   - Containers: distroless static, non-root, no shell.
   - RBAC: minimum-necessary for the CRD's group/resources.
   - Pod Security: `restricted` profile by default.
6. **Supply chain**
   - SBOM (CycloneDX) generated for every release.
   - Container images and wheels signed with Sigstore.
   - SLSA Level 3 build provenance attestation.
7. **Secret hygiene** — see [ADR-0012](0012-api-key-and-secret-management.md).
8. **Privacy**
   - Prompt and response capture is **off** by default.
   - When enabled, capture is local-only unless the user explicitly
     configures a remote sink. The configuration flag is named
     `--capture-prompts` to make it impossible to enable accidentally.

### Vulnerability response

- A `SECURITY.md` documents reporting channels (already exists in the
  repository — keep current).
- 90-day private disclosure window before public advisory.
- CVEs filed for high-severity issues.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Treat as low-risk dev tool | Faster shipping | Generates code that runs with cluster privileges; not low-risk |
| Outsource to one provider's policy | Less work | Couples to that provider; we have multiple |
| Heavyweight zero-trust framework | Maximum security | Disproportionate for a CLI tool; sets expectations we cannot meet |

## Consequences

### Positive
- Contributors and reviewers have a single document against which to test
  changes.
- Generated artefacts inherit secure defaults users would otherwise have to
  remember.
- Supply-chain story is enterprise-grade.

### Negative / Trade-offs
- Some hardening (signing, SBOM, attestation) adds release-pipeline cost.
- Defaults are stricter than some users want; opt-out flags exist but log
  loudly.

### Neutral
- The threat model is reviewed at every minor release.

## Related Decisions

- ADR-0003: Use OpenRouter as the primary LLM provider with pluggable backends
- ADR-0009: Graceful degradation to demo mode when AI is unavailable
- ADR-0012: Environment-variable-based API key and secret management
- ADR-0013: Filesystem as the artifact store for generated specs
- ADR-0017: Observability and telemetry strategy
- ADR-0019: Versioning, release, and packaging strategy
- DDD: `docs/ddd/07-anti-corruption-layers.md`
