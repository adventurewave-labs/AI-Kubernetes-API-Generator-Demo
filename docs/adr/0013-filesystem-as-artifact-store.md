# ADR-0013: Filesystem as the artifact store for generated specs

## Status

Accepted — 2025-05-09

## Context

The system generates artefacts (OpenAPI documents, CRDs, sample instances,
Go scaffolds) that downstream tools (`kubectl apply`, `go build`, GitOps
controllers) consume from disk. We must decide how those artefacts are
persisted, named, versioned, and located.

Options range from "scatter `.json` files in the working directory" to
"push every generation result to a Git repository as an immutable commit".

## Decision

The default artefact store is the **local filesystem**, with the following
contract:

1. The output root is configurable per request (`--output-dir`,
   `CodegenRequest.output_dir`) and defaults to
   `./generated_specs/<kind>/`.
2. Inside the output root, the generator produces a deterministic layout:

   ```
   <output_root>/
   ├── openapi.json                              ← OpenAPI 3.0 IR
   ├── <kind>.crd.yaml                           ← CRD manifest
   ├── <kind>.instance.yaml                      ← sample instance
   ├── controller/                               ← optional Go scaffold
   │   ├── main.go
   │   ├── api/<version>/<kind>_types.go
   │   ├── internal/controller/<kind>_controller.go
   │   ├── Dockerfile
   │   └── go.mod
   └── manifest.json                             ← provenance record
   ```

3. `manifest.json` records:
   - Tool version and commit (`docs/adr/0019-versioning-release-and-packaging.md`).
   - Timestamp.
   - Source `CodegenRequest`.
   - LLM provider, model, mode (live / demo).
   - SHA-256 of every artefact in the directory.

4. Generation is **idempotent**: regenerating with the same input produces
   byte-identical output (modulo timestamps that are explicitly factored
   into `manifest.json`). This is required for golden-file tests
   ([ADR-0018](0018-test-pyramid-strategy.md)).

5. The filesystem store is a single implementation of an
   `ArtifactRepository` port. Future adapters (Git, S3, OCI artefact
   registry) plug in without changing domain code.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| In-memory only | Pure pipeline | Users need files on disk for `kubectl`, `go build` |
| Git repository per request | Built-in versioning | Operational overhead; many users do not want a repo per generation |
| OCI artefact registry | Cloud-native | Heavy default; better as an opt-in adapter |
| SQLite database of manifests | Queryable | Tools like `kubectl` cannot read it directly |

## Consequences

### Positive
- Zero-configuration: every user already has a filesystem.
- Generated artefacts are diffable, reviewable, and committable to whatever
  repo the user chooses.
- Idempotency unlocks deterministic testing.

### Negative / Trade-offs
- No built-in history; users must commit to Git themselves to keep
  history.
- File ownership and permissions are the user's responsibility.

### Neutral
- The provenance manifest is the basis for future supply-chain attestations
  (in-toto / SLSA), recorded in [ADR-0020](0020-security-threat-model-and-hardening.md).

## Related Decisions

- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0018: Test pyramid: unit / integration / e2e / golden-file
- ADR-0019: Versioning, release, and packaging strategy
- ADR-0020: Security threat model and hardening posture
- DDD: `docs/ddd/bounded-contexts/03-artifact-generation.md`
