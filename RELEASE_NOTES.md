# Release Notes — v1.0.0

**Released:** 2026-06-13
**Tag:** `v1.0.0`
**Package:** [`ai-platform-generator`](https://pypi.org/project/ai-platform-generator/) (PyPI)
**Container:** `ghcr.io/marcuspat/ai-kubernetes-api-generator-demo:v1.0.0`

> **Headline:** v1.0.0 is the first stable release of the AI Kubernetes API
> Generator — a single command that turns a plain-English description of a
> Kubernetes API into a complete, signed artifact bundle (CRD, sample
> instance, OpenAPI spec, Go controller scaffold, kustomization, MCP server)
> in under one second. It runs fully offline in demo mode, or against any
> OpenRouter / OpenAI model. The output is byte-deterministic, SHA-256
> checksummed, and built on a strict hexagonal/DDD architecture documented
> across 20 ADRs and 14 design documents.

---

## What's included

### Core capabilities

- **Natural-language → Kubernetes API.** Describe the resource you want in
  English; receive a complete, kustomizable bundle.
- **Six artifact generators** ship by default and run on every invocation:
  | Generator | Output |
  |---|---|
  | `openapi` | Canonical OpenAPI 3.0 IR as `openapi.json` |
  | `crd` | `<kind>.crd.yaml` (`apiextensions.k8s.io/v1`) |
  | `instance` | `<kind>.instance.yaml` sample CR |
  | `go_controller` | controller-runtime scaffold (`main.go`, types, reconcile loop, `Dockerfile`, `Makefile`, `go.mod`) |
  | `mcp_server` | Optional MCP server scaffold for LLM tool use |
  | `kustomization` | `kustomization.yaml` overlay referencing the CRD + instance |
- **Eight canonical scenarios** ship as a built-in offline catalogue:
  PostgresCluster, RedisCluster, VectorDB, Notebook, DatabaseBackup,
  CacheCluster, MonitoringService, MLPipeline.

### Architecture (rock-solid foundation)

- **Hexagonal ports & adapters** with strict dependency inversion (ADR-0014).
- **6 bounded contexts** (DDD): Intent Interpretation, API Modelling,
  Artifact Generation, Cluster Provisioning, User Interaction, Observability.
- **7 Protocol ports** + 4 LLM adapters (OpenRouter, OpenAI, Demo, Fake) +
  2 repository adapters + 1 cluster-runtime adapter + 5 telemetry sinks.
- **`GenerationOrchestrator` saga** with explicit recovery rules and
  compensating actions (ADR-0009, ADR-0010).
- **35-event domain catalogue** with structured logging, OTEL traces, and a
  metric catalogue documented in `docs/ddd/bounded-contexts/06-observability.md`.

### Production-grade quality gates

| Gate | Status |
|---|---|
| `ruff check src/ tests/` | 0 issues |
| `mypy --strict` | 0 errors across 128 source files |
| Unit + golden tests | **1 424** passed, 6 environment-gated skips |
| E2E (no-cluster) | 9 passed |
| Performance | 25 benchmarks — all ≥ 25× faster than budget |
| Determinism | Postgres CRD checksum reproducible across sessions |

### Security

- **Path-traversal guards** on every filesystem write.
- **Secret redaction** before any payload leaves the process.
- **Generated controllers** are distroless, non-root (uid 65532), no
  wildcard RBAC, `-trimpath` + `-ldflags="-s -w"`.
- **SHA-256 provenance manifest** ships with every bundle.
- **CycloneDX SBOM** generated in CI on every tag.
- **Cosign-signed** container images via the release workflow.

### Developer experience

- **`generate`, `build`, `interactive`, `examples`, `validate`, `runs`,
  `cluster`** — seven Click commands with TTY, JSON, and quiet renderers.
- **Stable exit codes** (`0` / `11` / `15` / …) mapped per ADR-0016.
- **`./run.sh demo`** orchestrates the whole flow: prerequisite check,
  Kind cluster ensure, generate, apply, verify, summary.
- **Pre-built `Makefile` targets:** `lint`, `test`, `test-golden`,
  `wheel`, `sdist`, `release`, `image`, `sbom`, `check-release`, `e2e`,
  `shellcheck`, `demo-offline`.

---

## Installation

### From PyPI

```bash
pip install ai-platform-generator
```

Requires **Python ≥ 3.11**.

### From source

```bash
git clone https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo.git
cd AI-Kubernetes-API-Generator-Demo
pip install -e ".[dev]"
```

### Container

```bash
docker pull ghcr.io/marcuspat/ai-kubernetes-api-generator-demo:v1.0.0
```

---

## Quickstart

### Offline (no API key required)

```bash
python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=demo \
  --no-deploy \
  --output-dir ./output \
  generate "Create a PostgresCluster API with replicas (integer 1-7), \
            storageGiB (integer), backupSchedule (string), and tlsEnabled (boolean)"

# 14 files appear under ./output, including:
#   postgrescluster.crd.yaml       ← apply with kubectl
#   postgrescluster.instance.yaml  ← edit and apply
#   manifest.json                  ← SHA-256 of every file
```

### With a live LLM

```bash
export OPENROUTER_API_KEY="..."

python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=openrouter \
  --no-deploy \
  --output-dir ./output \
  generate "Redis cluster with memoryGiB, port (1-65535), and persistence"
```

### End-to-end on a local Kind cluster

```bash
./run.sh demo
# installs kind/kubectl if missing, brings up the cluster,
# generates the bundle, applies it, prints the summary
```

---

## Breaking changes

This is the first stable release. Compared with the pre-1.0 development snapshots:

- **Python ≥ 3.11** is now required (was 3.8+ in the prototype).
- The legacy CLI entry point `examples/ai_demo.py` is removed. Use
  `python -m ai_platform_generator.adapters.cli.main` (or `make demo`, or
  `./run.sh demo`).
- `--llm-provider=fake` is a test-only adapter and is documented as such.
  End users should pick `demo` (offline) or `openrouter` / `openai` (online).
- `OPENROUTER_MODEL` env var defaults moved from a 3B free model to the
  configurable per-call `--model` flag.
- The on-disk artifact layout is now uniform across all generators
  (see `docs/ddd/bounded-contexts/03-artifact-generation.md §6`).

If you used the pre-1.0 prototype, migration takes minutes — the README
quickstart is the new canonical path.

---

## Documentation

- **[`README.md`](README.md)** — install, quickstart, CLI reference.
- **[`docs/use-case-guide.md`](docs/use-case-guide.md)** — five persona-based
  walkthroughs (platform engineer, app developer, DevEx lead, conference
  demo, CI/CD integration).
- **[`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md)** — complete
  v1.0.0 validation evidence with verbatim command I/O.
- **[`docs/cli-validation-report.md`](docs/cli-validation-report.md)** —
  exhaustive per-command CLI validation.
- **[`docs/adr/`](docs/adr/)** — 20 Architecture Decision Records, all Accepted.
- **[`docs/ddd/`](docs/ddd/)** — 14 Domain-Driven Design documents covering
  domain vision, ubiquitous language, strategic + tactical design, the event
  catalogue, application services, and anti-corruption layers.
- **[`docs/RELEASE_PROCEDURE.md`](docs/RELEASE_PROCEDURE.md)** — reusable
  release runbook for v1.1, v2.0, and beyond.
- **[`docs/security/go-scaffold-review.md`](docs/security/go-scaffold-review.md)** —
  threat model for the generated Go controller.

---

## Acknowledgements

Built on the shoulders of:

- [Pydantic v2](https://docs.pydantic.dev/) — typed aggregates and value objects.
- [Click](https://click.palletsprojects.com/) + [Rich](https://github.com/Textualize/rich) — the CLI surface.
- [Jinja2](https://jinja.palletsprojects.com/) — deterministic template rendering with `StrictUndefined`.
- [structlog](https://www.structlog.org/) — structured logging with TTY/JSON/quiet renderers.
- [hatchling](https://hatch.pypa.io/) — packaging backend.
- The Kubernetes [CRD structural schema](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/) team.
- [OpenRouter](https://openrouter.ai/) for making model access trivially uniform.
- The [kubebuilder](https://book.kubebuilder.io/) project — the Go controller scaffold layout follows its conventions.

Thanks to everyone who fielded design questions during the 8-wave build-out
and to the security reviewers who pressure-tested the generated controller
scaffold.

---

## Upgrade path

There is no upgrade — this is v1.0.0. Future releases will follow
[Semantic Versioning](https://semver.org/) per the procedure in
[`docs/RELEASE_PROCEDURE.md`](docs/RELEASE_PROCEDURE.md).

## Verifying this release

```bash
# 1. Verify the wheel checksum matches the GitHub Release attachment
sha256sum ai_platform_generator-1.0.0-py3-none-any.whl

# 2. (Container) Verify the cosign signature
cosign verify ghcr.io/marcuspat/ai-kubernetes-api-generator-demo:v1.0.0 \
  --certificate-identity-regexp '.*' --certificate-oidc-issuer-regexp '.*'

# 3. (Generated bundles) Verify SHA-256 of every file against manifest.json
python -c "
import hashlib, json, sys
from pathlib import Path
m = json.loads(Path('manifest.json').read_text())
for f in m['files']:
    got = hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()
    print('OK ' if got == f['checksum']['value'] else 'BAD ', f['path'])
"
```
