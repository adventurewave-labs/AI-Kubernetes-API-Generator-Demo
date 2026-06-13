# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

(no entries yet)

## [1.0.0] - 2026-06-13

First public release: documentation-driven implementation from scratch — Waves 1–8.

### Added
- ADR-0001 through ADR-0020 adopted as the canonical architecture record — see `docs/adr/`.
- Domain-Driven Design corpus: 20 ADRs and 14 DDD documents (`docs/adr/`, `docs/ddd/`).
- Hexagonal ports-and-adapters architecture with strict dependency inversion (ADR-0014).
- 6 bounded contexts: Intent Interpretation, API Modelling, Artifact Generation, Cluster Provisioning, User Interaction, Observability (`docs/ddd/bounded-contexts/`).
- Value-object core: `GVK`, `SpecProperty`, `PropertyConstraints`, `OutputPath`, `Checksum`, `RunId`, `Intent` (ADR-0008).
- Error taxonomy `PlatformGeneratorError` with stable codes and `FieldViolation` payloads (ADR-0016).
- Domain-event envelope plus 35 catalogued event subclasses and an `EventBus` with context filters (ADR-0017).
- 7 Protocol-based ports — `LlmProvider`, `ArtifactRepository`, `ClusterRuntime`, `SecretProvider`, `TelemetrySink`, `Clock`, `RunRepository` (ADR-0014).
- Aggregates `CodegenRequest`, `OpenAPIDocument`, `ArtifactBundle`, `GenerationRun`, `Cluster`, `Deployment` (`docs/ddd/04-aggregates-and-entities.md`).
- Application services and `GenerationOrchestrator` saga with compensating actions (`docs/ddd/06-application-services.md`).
- `ArtifactGenerator` Template-Method base with Jinja2 `StrictUndefined` renderer and idempotency verifier (ADR-0015).
- 6 artefact generators: OpenAPI, CRD YAML, Sample Instance, Go controller scaffold (kubebuilder), Kustomization, MCP server (ADR-0011).
- LLM provider abstraction with `OpenRouterLlmAdapter`, `OpenAiLlmAdapter`, `DemoModeLlmAdapter`, and composable `FallbackLlmProvider` (ADR-0003, ADR-0009).
- 8 canonical demo-mode scenarios catalogued for offline runs (`docs/ddd/08-implementation-roadmap.md` §10).
- `FilesystemArtifactRepository`, `EnvSecretProvider`, `DotenvSecretProvider`, `ChainSecretProvider`, optional `KeyringSecretProvider`, `JsonlRunRepository` (ADR-0012, ADR-0013).
- `KindClusterRuntime` wrapping `kind`/`kubectl`/`docker` with subprocess hygiene (ADR-0006).
- Observability adapters: `StructlogSink` (TTY/JSON/quiet), `OtelSink`, `MetricsRecorder`, `SpanCorrelator`, `EventDispatcher` (ADR-0017).
- Full CLI surface (Click + Rich) with TTY/JSON/Quiet renderers and stable exit-code mapping (ADR-0007, `docs/ddd/bounded-contexts/05-user-interaction.md`).
- CLI commands: `build`, `generate`, `interactive`, `examples`, `cluster`, `runs`, `validate` (`docs/ddd/bounded-contexts/05-user-interaction.md`).
- Golden-file regression matrix: 8 scenarios × 6 generators, idempotency-verified (ADR-0018).
- pytest-benchmark performance suite covering IR builder, CRD generator, artifact bundle, and full-saga paths (ADR-0018).
- `run.sh` end-to-end demo wrapper with `install-tools`/`cluster-up`/`cluster-down`/`demo` subcommands and offline mode (ADR-0009).
- Multi-arch (`linux/amd64` + `linux/arm64`) container image built distroless and non-root (uid 65532) (ADR-0019, ADR-0020).
- Tag-triggered GitHub Actions release pipeline: build, image push to GHCR, cosign signing, SLSA build-provenance, PyPI trusted publishing, GitHub Release (ADR-0019).
- CycloneDX SBOM generation workflow on push to `main` and on tags (ADR-0019).
- Stdlib-only `scripts/release/check_release.py` guard for tag/version/CHANGELOG/working-tree invariants (ADR-0019).
- `shellcheck` wrapper `scripts/shellcheck-runsh.sh` plus `make shellcheck` target (ADR-0020).
- `Makefile` targets for `wheel`, `sdist`, `release`, `image`, `sbom`, `check-release`, `e2e`, `shellcheck`, `demo-offline` (ADR-0019).

### Changed
- Minimum supported Python raised to 3.11 across `pyproject.toml`, `[tool.mypy]`, and the release workflow matrix (ADR-0002).
- `DemoModeLlmAdapter` now emits payloads in the legacy intent shape so the offline demo always parses into a valid `CodegenRequest` (`docs/ddd/bounded-contexts/01-intent-interpretation.md`).
- `LlmProvider` Protocol widened: `name`, `model`, `mode` are read-only `@property` so both adapter-style attributes and fallback-style properties satisfy it (ADR-0014).
- Generated Go controller Dockerfile now passes `-trimpath` and `-ldflags="-s -w"` and runs `go mod download -mod=readonly` (ADR-0020).
- Generated Go controller defaults `zap.Options{Development: false}` for production-safe logs (ADR-0020).
- `ArtifactType` migrated from `(str, Enum)` to `StrEnum` for forward compatibility (ADR-0008).
- `datetime.timezone.utc` replaced with `datetime.UTC` across the codebase (ADR-0002).

### Deprecated
- Legacy prototype modules `agent.py`, `cli.py`, `cluster_manager.py`, `codegen.py` retained for reference but excluded from ruff/mypy and slated for removal (`docs/ddd/08-implementation-roadmap.md`).

### Removed
- `Python :: 3.10` classifier and 3.10 CI matrix entry (ADR-0002).
- Six stale `# type: ignore` comments — types-PyYAML and the openai SDK now ship complete stubs (ADR-0014).
- `mix_stderr=False` kwarg from Click 8.2 `CliRunner` callsites (`docs/ddd/bounded-contexts/05-user-interaction.md`).

### Fixed
- `DemoModeLlmAdapter` no longer raises `E_DOMAIN_GENERIC: missing 'group'` on the offline demo path (`docs/ddd/bounded-contexts/01-intent-interpretation.md`).
- `validate` CLI command translates `KeyError`/`ValueError` on `CodegenRequest.from_dict` into `DomainValidationError` so missing-required-field maps to exit 11 (`docs/ddd/bounded-contexts/05-user-interaction.md`).
- `cluster_provisioning.verify()` raises `DeploymentVerificationFailed` explicitly on a missing GVK rather than silently passing `Any` (ADR-0016).
- `_resolve_log_format` narrowed to `Literal["tty", "json", "quiet"]` so renderer selection is total (`docs/ddd/bounded-contexts/05-user-interaction.md`).
- Prerequisite-missing failures in `run.sh` now exit 15 to match the CLI exit-code map (`docs/ddd/bounded-contexts/05-user-interaction.md` §7).

### Security
- Secret redaction layer (`SecretRedactor` + `RedactionPolicy.default()`) applied to every telemetry payload before it leaves the process (ADR-0017, ADR-0020).
- Generated Go controllers ship distroless + non-root (uid 65532), with no `apt-get`, no `RUN sh`, and no `USER root` (ADR-0020).
- Path-traversal guards on `FilesystemArtifactRepository` reject `..` segments and absolute escapes before any I/O (ADR-0013, ADR-0020).
- mypy `--strict` is clean across 128 source files with zero `# type: ignore` escape hatches surviving (ADR-0014, ADR-0020).
- Subprocess hygiene throughout: `shell=False`, mandatory timeouts, validated argv, `FileNotFoundError → PrerequisiteMissing` translation (ADR-0020).
- RBAC markers in the generated controller never use wildcard verbs; lock-in tests enforce this (ADR-0020).
- CycloneDX SBOM attached to every release (ADR-0019).

### Performance
- pytest-benchmark suite landed under `tests/performance/` covering IR builder, CRD generator, artifact bundle, and full-saga hot paths with explicit per-test budgets (ADR-0018).
<!-- Wave 8 chunk (4) appends here -->

[Unreleased]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/releases/tag/v1.0.0
