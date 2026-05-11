# Generated Go controller scaffold — security review

| Field        | Value |
| ------------ | ----- |
| Reviewer     | Agent W3 (Wave 8, swarm chunk 3) |
| Review date  | 2026-05-11 |
| Reviewed against | [ADR-0020 — Security threat model and hardening posture](../adr/0020-security-threat-model-and-hardening.md) |
| Reviewed code | `src/ai_platform_generator/domain/generation/generators/go_controller.py` and the Jinja templates under `src/ai_platform_generator/templates/go/` |
| Output git ref | `claude/adr-ddd-documentation-wcROb` @ 526b431 (pre-fix); fixes applied on the same branch in this PR |

## 1. Scope

This review covers **only the files emitted by `GoControllerGenerator`** — `main.go`,
`api/<version>/<kindLower>_types.go`,
`internal/controller/<kindLower>_controller.go`,
`Dockerfile`, `go.mod`, and `Makefile`.

Out of scope: the CRD generator (covered separately), the kustomize
overlay generator, the MCP server scaffold, the host CLI / Python
runtime hardening, and the ADR itself (which is the source of truth).

## 2. Methodology

The scaffold was materialised against the canonical `PostgresCluster`
scenario from `docs/ddd/08-implementation-roadmap.md §10` (and
cross-checked against the other seven canonical scenarios via the
existing golden-file fixtures). Reproduction:

```python
from pathlib import Path
from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import CodegenRequest, OpenAPIDocument
from ai_platform_generator.domain.generation.generators.go_controller import (
    GoControllerGenerator,
)

scenario = next(s for s in DemoCatalog().scenarios if s.name == "postgres-cluster")
req = CodegenRequest.from_dict(scenario.request)
ir = OpenAPIDocument.from_request(req)

out = Path("/tmp/audit-go-scaffold")
out.mkdir(parents=True, exist_ok=True)
for art in GoControllerGenerator().generate(ir, out):
    target = out / art.path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(art.payload)
```

Each emitted file was inspected against the ADR-0020 hardening
checklist; findings are recorded below.

## 3. Findings

| ID  | Severity | Component     | Description                                                                 | Resolution |
| --- | -------- | ------------- | --------------------------------------------------------------------------- | ---------- |
| F-01 | Medium | `Dockerfile.j2` | `RUN go mod download` ran without `-mod=readonly`, so a build could silently mutate dependencies and bypass any committed `go.sum`. | **Fixed in this PR.** Build command now includes `-mod=readonly`; `go.sum` is copied (via a glob so the file remains optional pre-`go mod tidy`). |
| F-02 | Medium | `Dockerfile.j2` | `go build` did not pass `-trimpath`, leaking the builder's absolute filesystem paths into the compiled binary (information disclosure under STRIDE). | **Fixed in this PR.** `-trimpath` added; `-ldflags="-s -w"` also strips the symbol table for a smaller, less-fingerprintable artefact. |
| F-03 | Medium | `main.go.j2`   | Controller defaulted `zap.Options{Development: true}`, producing verbose, console-formatted logs that stamp reconciled-object contents into stdout — counter to the "secret hygiene" commitment in ADR-0020 and not the right default for an artefact users deploy to production clusters. | **Fixed in this PR.** Default flipped to `Development: false` (structured JSON, sampled). Operators can still opt in via the standard `--zap-devel` CLI flag. |
| F-04 | Low | `Dockerfile.j2` | Builder image is pinned to a major.minor (`golang:1.22`) but not a digest. Acceptable per project policy — pinning by digest would force a generator change on every upstream Go patch release. | Accepted. Documented in the Dockerfile header comment; revisit when SLSA Level 3 release pipeline (ADR-0019) is wired in and can rewrite the digest automatically. |
| F-05 | Low | `Dockerfile.j2` | Runtime base `gcr.io/distroless/static:nonroot` is similarly not digest-pinned. | Accepted (same reasoning as F-04). |
| F-06 | Low | RBAC markers | The `kubebuilder:rbac` markers grant `get;list;watch;create;update;patch;delete` on the CRD's own resources. The stub reconciler only reads; the write verbs are present for future user code. | Accepted. The verbs are explicit (no `*`), scoped to the CRD's own group + plural + `/status` + `/finalizers`, and follow the standard kubebuilder template. Tightening below the kubebuilder norm would surprise downstream users who add reconciliation logic. |
| F-07 | Info | `Makefile.j2` | Generated `Makefile` references `config/crd`, `config/manager`, `config/default` directories that this generator does not currently emit. | Deferred. Not a security issue — the generator only emits six files by design (ADR-0011). Users who run the make targets will see a kustomize error; tracked as a usability bug, not a hardening gap. |
| F-08 | Info | Pod Security  | No `PodSecurityStandards` manifest (PSA `restricted` profile) is emitted; ADR-0020 §"Generated-artefact hardening" lists it as a commitment. | Deferred to the kustomize-overlay generator (separate component); the `GoControllerGenerator`'s six-file scope (ADR-0011) does not include cluster-side policy manifests. Filed as a backlog item against the kustomization generator. |
| F-09 | Info | `controller.go.j2` | No `os/exec`, `syscall`, or `unsafe` imports in the emitted reconciler. | No action — verified clean. |
| F-10 | Info | `go.mod.j2`   | Every `require` entry is pinned to a concrete semver (`k8s.io/api v0.30.3`, `sigs.k8s.io/controller-runtime v0.18.4`, …). No `v0.0.0-*` pseudo-versions, no `master`. | No action — verified clean. |
| F-11 | Info | `controller.go.j2` | The reconciler stub does not embed any secret material; it references resources via the Kubernetes API only. | No action — verified clean. |

### Severity tally

| Severity | Count | Status |
| -------- | ----- | ------ |
| Critical | 0     | — |
| High     | 0     | — |
| Medium   | 3     | All fixed in this PR (F-01, F-02, F-03) |
| Low      | 3     | Accepted with rationale (F-04, F-05, F-06) |
| Info     | 5     | Two deferred (F-07, F-08); three verifications recorded (F-09, F-10, F-11) |

## 4. Verification

The fixes are locked in by:

1. **Golden-file regeneration.** `tests/golden/expected/<scenario>/go_controller/` was refreshed via `pytest tests/golden/generators --update-golden`, so any future template regression will fail the byte-strict golden assertions. Re-run with `make test-golden`.
2. **Targeted hardening assertions** in
   `tests/unit/generation/generators/test_go_scaffold_security.py` —
   added in this PR. It asserts:
   * `Dockerfile` contains `distroless/static` and `USER 65532:65532`.
   * `Dockerfile` does **not** contain `apt-get`, `RUN sh`, `USER root`,
     or `ARG.*PASSWORD`-style secret leaks.
   * `Dockerfile` builds with `-mod=readonly` and `-trimpath`.
   * `main.go` defaults `zap.Options` to `Development: false`.
   * The reconciler does not import `os/exec`, `syscall`, or `unsafe`.
   * Every `+kubebuilder:rbac:` marker has explicit verbs (no `*`) and
     no wildcard group/resource.
   * Every `require` entry in `go.mod` is pinned to a concrete semver
     (no `v0.0.0-`, no `master`, no missing version).

## 5. STRIDE coverage — generated scaffold

| STRIDE threat | Mitigation called out in ADR-0020 | Generated scaffold defense |
| ------------- | --------------------------------- | -------------------------- |
| Spoofing (LLM provider) | TLS / cert pinning option | n/a — scaffold does not talk to the LLM |
| Tampering (generated artefacts) | SHA-256 digests in `manifest.json`; signed releases | partial — digests are emitted by the host generator; signing is host-side (ADR-0019) |
| Tampering (LLM responses) | JSON-schema validation | n/a — scaffold has no LLM dependency |
| Repudiation (generation audit) | Provenance manifest | partial — provenance is emitted alongside the scaffold; not part of the six files |
| Information disclosure (API keys) | Redacting log layer | yes — controller logs default to structured JSON (F-03 fix); secrets are read from Kubernetes Secret objects, not embedded |
| Information disclosure (build paths) | n/a in ADR | yes — `-trimpath` (F-02 fix) |
| Denial of service (LLM rate limits) | Backoff, demo fallback | n/a |
| Denial of service (local exhaustion) | Subprocess timeouts, input caps | partial — the generator's own `gofmt` subprocess has a 10 s timeout; the emitted controller respects controller-runtime's manager timeouts |
| Elevation of privilege (controllers) | Distroless, non-root UID `65532`, scoped RBAC | yes — distroless/static:nonroot, USER 65532:65532, RBAC scoped to the CRD's group + plural |
| Prompt injection | System prompt isolation; never exec LLM output | n/a — scaffold is not LLM-driven at runtime |
| Supply chain | Pinned hashes, SBOM, signed releases | partial — `go.mod` versions pinned (F-10), `-mod=readonly` enforces `go.sum` (F-01); SBOM and signing are host-side (ADR-0019) |

Legend: **yes** = covered by the scaffold itself; **partial** = covered
in part by the scaffold and in part by the host pipeline; **n/a** = the
threat does not apply to the generated artefact.

## 6. Open items

* Wire a PSA `restricted` policy into the kustomize-overlay generator
  (F-08).
* Once the release pipeline (ADR-0019) is in place, switch builder and
  runtime base images to digest pins (F-04, F-05).
* Emit a `config/` tree so the `Makefile` targets line up with the
  files actually shipped (F-07).

None of the open items are blockers for the v1 hardening commitments;
all three are tracked against the kustomization/release-pipeline
backlog, not against `GoControllerGenerator`.
