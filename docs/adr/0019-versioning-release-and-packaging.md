# ADR-0019: Versioning, release, and packaging strategy

## Status

Accepted — 2025-05-09

## Context

Three distinct artefacts have versions in this project:

1. The **generator tool itself** (Python package `ai_platform_generator`).
2. The **OpenAPI IR schema** that flows through the pipeline
   ([ADR-0004](0004-openapi-3-as-intermediate-representation.md)).
3. The **CRDs / controllers** the user generates (`v1alpha1`, `v1beta1`,
   etc.).

These have independent lifecycles. Conflating them would either pin the
tool to its first CRD version or force users to bump CRDs every time we
ship a bugfix.

## Decision

### Tool versioning

- The generator follows **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`).
- `MAJOR` bumps for: breaking changes to the CLI, breaking changes to the
  error taxonomy ([ADR-0016](0016-validation-pipeline-error-model.md)), or
  output format changes that break golden-file consumers.
- `MINOR` bumps for: new commands, new artefact generators, new
  ports/adapters.
- `PATCH` bumps for: bug fixes, internal refactors.
- The version is the single source of truth in `pyproject.toml`; everything
  else (Docker tag, generated-artefact provenance) reads from there.

### IR versioning

- The OpenAPI IR is pinned to a `x-platform-generator-ir` extension version,
  starting at `1.0.0` and following the same semver rules. Breaking
  changes to the IR are major-tool changes.

### CRD versioning

- Generated CRDs default to `v1alpha1` and the generator emits a clear
  warning that promotion to `v1beta1` / `v1` requires a conversion strategy
  the user must own.
- The generator can produce *multiple stored versions* for a single CRD
  when the user supplies a conversion configuration; this is gated behind
  a feature flag until a future ADR formalises conversion-webhook
  generation.

### Packaging

- Distributed as:
  1. A **PyPI package** (`pip install ai-platform-generator`).
  2. A **container image** published to `ghcr.io/marcuspat/ai-platform-generator`,
     multi-arch (`linux/amd64`, `linux/arm64`).
  3. Pre-built single-file binaries via `pyinstaller` for macOS, Linux,
     Windows on each tagged release.
- Wheel and image are signed with **Sigstore / cosign**; provenance is
  attested via SLSA build-level metadata.

### Release process

- **Trunk-based** development on `main`.
- Tags `vMAJOR.MINOR.PATCH` cut from `main` trigger the release pipeline.
- Pre-releases use `vMAJOR.MINOR.PATCH-rcN` and publish to a
  `--pre`-tagged PyPI / `*-rcN` container tag.
- A `CHANGELOG.md` is generated from Conventional Commit messages and is
  part of the release commit.

### Deprecation policy

- Any feature deprecation lives for **at least one minor cycle** with a
  warning before removal.
- Removed features are listed in the CHANGELOG under "Breaking changes"
  with a migration note.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| CalVer | Predictable cadence | Hides intent; users rely on knowing what changed |
| 0.x forever | No backwards-compat promises | Disincentivises rigorous deprecation; users dislike it |
| Single-version-for-everything | Simple | Couples unrelated lifecycles |
| Conda-only / Homebrew-only | Niche audiences | Both are first-class but not exclusive |

## Consequences

### Positive
- Predictable upgrade story for users.
- The provenance manifest ([ADR-0013](0013-filesystem-as-artifact-store.md))
  records the exact tool version that produced an artefact.
- Container and wheel signing aligns with supply-chain expectations
  ([ADR-0020](0020-security-threat-model-and-hardening.md)).

### Negative / Trade-offs
- Multi-target packaging adds release-pipeline complexity.
- Maintaining a Conventional Commit discipline is a small ongoing cost.

### Neutral
- The tool-version / CRD-version distinction is documented in
  user-facing release notes.

## Related Decisions

- ADR-0004: Adopt OpenAPI 3.0 as the canonical intermediate representation
- ADR-0013: Filesystem as the artifact store for generated specs
- ADR-0016: Validation pipeline with explicit error model
- ADR-0020: Security threat model and hardening posture
