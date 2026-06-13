# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] — 2026-06-12

Full DDD + hexagonal-architecture rewrite (Waves 1–8). First release after v1.0.1 prototype tags.

### Added

- ADR-0001 through ADR-0020 adopted as the canonical architecture record (docs/adr/).
- Domain-Driven Design corpus — 20 ADRs and 14 DDD documents (docs/adr/, docs/ddd/).
- Hexagonal ports-and-adapters architecture with strict dependency inversion (ADR-0014).
- 6 bounded contexts: Intent Interpretation, API Modelling, Artifact Generation, Cluster Provisioning, User Interaction, Observability.
- Value-object core — GVK, SpecProperty, PropertyConstraints, OutputPath, Checksum, RunId, Intent (ADR-0008).
- Error taxonomy — PlatformGeneratorError with stable exit codes and FieldViolation payloads (ADR-0016).
- Domain-event system — event envelope, 35 catalogued event subclasses, EventBus with context filters (ADR-0017).
- 7 Protocol-based ports — LlmProvider, ArtifactRepository, ClusterRuntime, SecretProvider, TelemetrySink, Clock, RunRepository (ADR-0014).
- Aggregates — CodegenRequest, OpenAPIDocument, ArtifactBundle, GenerationRun, Cluster, Deployment.
- Application services and GenerationOrchestrator saga with compensating actions.
- ArtifactGenerator Template-Method base — Jinja2 StrictUndefined renderer + idempotency verifier (ADR-0015).
- 6 artifact generators — OpenAPI, CRD YAML, Sample Instance, Go controller scaffold (kubebuilder), Kustomization, MCP server (ADR-0011).
- LLM adapters — OpenRouterLlmAdapter, OpenAiLlmAdapter, DemoModeLlmAdapter, FallbackLlmProvider (ADR-0003, ADR-0009).
- 8 canonical demo-mode scenarios for fully offline runs.
- Infrastructure adapters — FilesystemArtifactRepository, EnvSecretProvider, DotenvSecretProvider, ChainSecretProvider, KeyringSecretProvider, JsonlRunRepository.
- KindClusterRuntime wrapping kind/kubectl/docker with subprocess hygiene.
- Observability adapters — StructlogSink (TTY/JSON/quiet), OtelSink, MetricsRecorder, SpanCorrelator, EventDispatcher.
- Full CLI (Click + Rich) with TTY/JSON/Quiet renderers and stable exit-code mapping (ADR-0007).
- CLI commands — build, generate, interactive, examples, cluster, runs, validate.
- Golden-file regression matrix — 8 scenarios x 6 generators (62 cells), idempotency-verified.
- pytest-benchmark suite — 25 benchmarks covering IR builder, CRD generator, artifact bundle, full-saga (ADR-0018).
- run.sh — end-to-end demo wrapper (install-tools/cluster-up/cluster-down/demo).
- Multi-arch container image — linux/amd64 + linux/arm64, distroless, non-root uid 65532 (ADR-0019, ADR-0020).
- Tag-triggered release pipeline — GitHub Actions: build, GHCR push, cosign signing, SLSA provenance, PyPI trusted publishing, GitHub Release (ADR-0019).
- CycloneDX SBOM — generated on push to main and on every release tag.
- scripts/release/check_release.py — stdlib-only release-invariant guard.
- Makefile — wheel, sdist, release, image, sbom, check-release, e2e, shellcheck, demo-offline targets.
- CLI validation report (docs/cli-validation-report.md) — per-command I/O capture, exit-code contract, determinism proof.
- Use-case guide (docs/use-case-guide.md) — persona-based guide for operator, developer, and platform teams.

### Changed

- Minimum supported Python raised to 3.11 across pyproject.toml, [tool.mypy], and release workflow matrix (ADR-0002).
- DemoModeLlmAdapter emits payloads in the legacy intent shape so the offline demo always parses into a valid CodegenRequest.
- LlmProvider Protocol widened — name, model, mode are read-only @property.
- Generated Go controller Dockerfile — -trimpath, hardened ldflags, go mod download -mod=readonly (ADR-0020).
- Generated Go controller defaults zap.Options{Development: false} for production-safe logs.
- ArtifactType migrated from (str, Enum) to StrEnum.
- datetime.timezone.utc replaced with datetime.UTC throughout (ADR-0002).

### Deprecated

- Legacy prototype modules (agent.py, cli.py, cluster_manager.py, codegen.py) retained for reference in src/ but excluded from linting and type checking. Scheduled for removal in v1.2.0.

### Removed

- Python 3.10 classifier and 3.10 CI matrix entry (ADR-0002).
- Six stale # type: ignore comments — types-PyYAML and the openai SDK now ship complete stubs.
- mix_stderr=False kwarg from Click 8.2 CliRunner call sites.

### Fixed

- DemoModeLlmAdapter no longer raises E_DOMAIN_GENERIC: missing group on the offline demo path (commit 4697818).
- build command no longer crashes with InvalidOutputPath when --output-dir receives an absolute path (commit 3ab67bb).
- interactive command no longer raises E_ARTIFACT_PATH_TRAVERSAL when --output-dir is set (commit 3ab67bb).
- validate CLI command translates KeyError/ValueError on CodegenRequest.from_dict into DomainValidationError, exit 11.
- cluster_provisioning.verify() raises DeploymentVerificationFailed explicitly on a missing GVK.
- Prerequisite-missing failures in run.sh now exit 15 (matches CLI exit-code map).

### Security

- Secret redaction layer (SecretRedactor + RedactionPolicy.default()) applied to every telemetry payload before it leaves the process.
- Generated Go controllers — distroless, non-root uid 65532, no apt-get, no RUN sh, no USER root (ADR-0020).
- Path-traversal guards on FilesystemArtifactRepository reject ../ segments and absolute escapes before any I/O; regression tests at tests/e2e/test_cli_output_dir.py.
- mypy --strict clean across 128 source files — zero # type: ignore escape hatches (ADR-0014, ADR-0020).
- Subprocess hygiene throughout — shell=False, mandatory timeouts, validated argv, FileNotFoundError mapped to PrerequisiteMissing.
- RBAC markers in generated controllers never use wildcard verbs; lock-in tests enforce this.
- CycloneDX SBOM attached to every release.

### Performance

- All 25 pytest-benchmark benchmarks within budget — IR builder ~25 us (50 ms budget), CRD generator ~1.8 ms (100 ms budget), full saga ~10 ms (1000 ms budget). Over 100x headroom end-to-end.

---

[Unreleased]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/v1.0.1...v1.1.0
