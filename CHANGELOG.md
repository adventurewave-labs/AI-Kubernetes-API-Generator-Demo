# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Domain-Driven Design corpus: 20 ADRs and 14 DDD documents
  (docs/adr/, docs/ddd/).
- Hexagonal architecture (ports + adapters) per ADR-0014.
- 6 bounded contexts: Intent Interpretation, API Modelling,
  Artifact Generation, Cluster Provisioning, User Interaction,
  Observability.
- 6 artefact generators: OpenAPI, CRD YAML, Sample Instance,
  Go controller scaffold (kubebuilder), Kustomization, MCP server.
- LLM provider abstraction with OpenRouter, OpenAI, Demo Mode, and
  pluggable Fallback composition.
- Full CLI surface (Click + Rich) with TTY/JSON/Quiet renderers and
  stable exit-code mapping.
- Telemetry: structured logs, metrics, OpenTelemetry traces (opt-in).
- Container image (multi-arch, distroless, non-root) and
  signed wheels with cosign + SLSA provenance.

### Security
- Path-traversal guards on FilesystemArtifactRepository.
- Subprocess hygiene (shell=False, mandatory timeouts, validated argv).
- Secret redaction layer for telemetry payloads.
- SBOM (CycloneDX) per release.

[Unreleased]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/HEAD...HEAD
