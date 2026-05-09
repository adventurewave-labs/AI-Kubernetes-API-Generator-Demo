# Bounded Context — Artifact Generation

> **Purpose:** turn the **OpenAPI IR** into a complete **Artifact Bundle** —
> CRD, sample instance, OpenAPI document, optional Go controller, optional
> MCP server — and persist it through the `ArtifactRepository` port.

This is a **supporting** subdomain. The IR carries the meaning; this
context is responsible for high-fidelity, deterministic *rendering* of
that meaning into many target shapes.

---

## 1. Responsibilities

1. Decide which generators to run for a given request (default set +
   user overrides).
2. Run each generator through the **Template Method** lifecycle
   ([ADR-0015](../../adr/0015-template-method-for-code-generation.md)).
3. Produce a `ProvenanceManifest` with checksums.
4. Persist via the `ArtifactRepository` port.
5. Guarantee idempotency: same input → byte-identical output.

This context **does not**:

- Talk to the LLM or the cluster.
- Change the IR (the IR is the contract; if it is wrong, it must be
  fixed in API Modelling).

## 2. Ubiquitous language

Originated here: **Artifact**, **Artifact Bundle**, **Artifact
Generator**, **Generation Plan**, **Rendered File**, **Post-processing**,
**Idempotency**, **Provenance Manifest**.

## 3. Aggregates and value objects

| Type                    | Pattern         | Notes                                                                      |
| ----------------------- | --------------- | -------------------------------------------------------------------------- |
| `ArtifactBundle`        | Aggregate root  | See `../04-tactical-design.md §4.3`.                                      |
| `ProvenanceManifest`    | Value object    | Embedded in the aggregate.                                                  |
| `RenderedArtifact`      | Value object    | `(path, bytes, mode, artefact_type, checksum)`.                            |
| `GenerationPlan`        | Value object    | Side-effect-free description of what will be written.                       |
| `ArtifactType`          | Enum            | `OPENAPI | CRD | INSTANCE | GO_CONTROLLER | MCP_SERVER | KUSTOMIZATION`.   |

## 4. Domain services

| Service                      | Responsibility                                                                    |
| ---------------------------- | --------------------------------------------------------------------------------- |
| `ArtifactPlanner`            | `(ir, target_dir, requested_types) -> GenerationPlan`.                            |
| `Renderer`                   | Jinja2 renderer with `StrictUndefined` and pre-loaded macros.                     |
| `PostProcessor` (per generator) | Runs `gofmt` / `yamlfmt` / `prettier` etc. as needed.                           |
| `ChecksumService`            | SHA-256 of `bytes`.                                                                |
| `IdempotencyVerifier`        | Re-runs a generator and asserts byte-equivalence (for golden tests).              |

## 5. Application service

`ArtifactGenerationService.run(ir, params) -> ArtifactBundle`:

1. Build a `GenerationPlan` for each requested generator.
2. Validate plans (no path collisions across generators).
3. Run each generator's `_render` then `_post_process`.
4. Assemble a `ArtifactBundle` and `ProvenanceManifest`.
5. Persist via `ArtifactRepository`.
6. Emit `ArtifactBundleSealed`.

## 6. Generator hierarchy

The base class is `ArtifactGenerator` (Template Method, see
[ADR-0015](../../adr/0015-template-method-for-code-generation.md)).
Concrete generators:

| Generator                    | Inputs from IR                                  | Outputs                                                                                   |
| ---------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `OpenApiGenerator`           | The IR itself                                   | `openapi.json` (the canonical IR JSON).                                                  |
| `CrdYamlGenerator`           | `Kind` schema, GVK, extensions                  | `<kind>.crd.yaml`.                                                                         |
| `InstanceYamlGenerator`      | `Kind` schema, sample values                    | `<kind>.instance.yaml`.                                                                    |
| `GoControllerGenerator`      | GVK, Spec schema                                | `controller/main.go`, `api/<v>/<kind>_types.go`, `internal/controller/<kind>_controller.go`, `Dockerfile`, `go.mod`. |
| `McpServerGenerator`         | The IR itself                                   | An MCP-server scaffold (future, optional).                                                  |
| `KustomizationGenerator`     | GVK, generated CRD path                         | `kustomization.yaml` referencing CRD + instance.                                            |

The default set is `OpenApi + Crd + Instance`. Users can request any
subset via `GenerateParams.requested_generators`.

### 6.1 Template Method skeleton

```python
class ArtifactGenerator(ABC):
    name: str
    artefact_type: ArtifactType

    def generate(self, ir: OpenAPIDocument, target: Path) -> list[RenderedArtifact]:
        self._check_preconditions(ir)
        plan = self._plan(ir, target)
        files = self._render(plan)
        files = self._post_process(files)
        return files

    @abstractmethod
    def _check_preconditions(self, ir): ...
    @abstractmethod
    def _plan(self, ir, target): ...
    @abstractmethod
    def _render(self, plan): ...
    def _post_process(self, files): return files
```

### 6.2 Concrete generator details

#### `CrdYamlGenerator`

- Maps `Kind` schema → `spec.versions[0].schema.openAPIV3Schema` (with
  `apiVersion` / `kind` / `metadata` stripped — Kubernetes injects them).
- Sets `served: true`, `storage: true`.
- `subresources: { status: {} }` always set.
- `scope` defaults to `Namespaced`; user override via future ADR.
- Emits printer columns from `KubernetesExtensions` if present.

#### `InstanceYamlGenerator`

- Generates a sample instance with name `my-<kindLower>-instance`.
- Fills each spec property with a *type-appropriate placeholder* taken
  from the IR's `default` if present, else from a deterministic stub
  table (`"example"`, `1`, `1.0`, `true`, `[]`, `{}`).

#### `GoControllerGenerator`

- Layout per [ADR-0011](../../adr/0011-go-controller-kubebuilder-scaffold.md).
- `_post_process` runs `gofmt -s` if available; if absent, emits a
  warning event and skips formatting.
- Pinned dependency versions live in `templates/go/go.mod.j2`.

#### `OpenApiGenerator`

- Just serialises the IR via `IRSerialiser`. Trivial but uniform.

## 7. Provenance manifest

`manifest.json` schema:

```jsonc
{
  "$schema": "https://platform-generator.io/schemas/manifest-1.0.0.json",
  "schema_version": "1.0.0",
  "run_id": "...",
  "tool_version": "0.4.2",
  "git_sha": "abc123",
  "generated_at": "2025-05-09T12:34:56Z",
  "request": { /* CodegenRequest as JSON */ },
  "provider": { "name": "openrouter", "model": "anthropic/claude-3.5-sonnet" },
  "provider_mode": "live",
  "files": [
    { "path": "openapi.json",                "type": "OPENAPI",       "sha256": "..." },
    { "path": "postgrescluster.crd.yaml",    "type": "CRD",           "sha256": "..." },
    { "path": "postgrescluster.instance.yaml","type": "INSTANCE",     "sha256": "..." }
  ]
}
```

A consumer can verify a bundle by:

1. Hashing each file in `files`.
2. Comparing to `sha256`.
3. Optionally verifying the manifest's own signature
   ([ADR-0019](../../adr/0019-versioning-release-and-packaging.md)).

## 8. Idempotency

`generate(ir, target)` is required to be idempotent. Tests:

- `IdempotencyVerifier`: run twice, diff bytes → must be empty.
- `tests/golden/`: checked-in expected output for the canonical scenarios.

When non-determinism is unavoidable (e.g. timestamps in `manifest.json`),
those fields are factored out by `IdempotencyVerifier` before comparison.

## 9. Domain events emitted

| Event                       | When                                                      |
| --------------------------- | --------------------------------------------------------- |
| `GenerationPlanned`         | After `_plan` for each generator.                         |
| `ArtifactRendered`          | After `_render` for each file.                            |
| `ArtifactPostProcessed`     | After `_post_process` for each file.                      |
| `ArtifactGenerated`         | After persisting each file.                               |
| `ArtifactBundleSealed`      | After the manifest is written and checksums verified.     |
| `ArtifactGenerationFailed`  | On any failure.                                            |

## 10. Failure modes

| Failure                          | Outcome                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------- |
| Path collision between generators | Caller bug — terminal.                                                          |
| Template rendering error          | Terminal `TemplateRenderingError`. Compensate: do not persist partial bundle.   |
| Post-processing tool missing      | Warn and skip (e.g. `gofmt` absent).                                            |
| Filesystem write failure          | Terminal `ArtifactWriteFailed`. Compensate: delete partial bundle.              |
| Checksum mismatch on read-back    | Terminal `ChecksumMismatch`.                                                    |

## 11. Public contract

Inputs:

- `OpenAPIDocument` (validated).
- `GenerateParams` (output dir, requested generators).

Output:

- `ArtifactBundle` (and a target directory on disk).

Errors:

- `ArtifactGenerationError` and subclasses
  ([ADR-0016](../../adr/0016-validation-pipeline-error-model.md)).

## 12. Testing strategy

- **Unit:** each generator's `_plan` and `_render` with fake IRs.
- **Integration:** writes through `FilesystemArtifactRepository` with
  `tmp_path`.
- **Golden:** the canonical scenarios.
- **Property:** any well-formed IR produces a bundle whose every checksum
  matches.

## 13. Extending: how to add a generator

1. Subclass `ArtifactGenerator` in
   `domain/generation/generators/<name>.py`.
2. Set `name`, `artefact_type`.
3. Implement `_check_preconditions`, `_plan`, `_render`.
4. Add templates under `templates/<name>/`.
5. Register the generator in `default_generators()` if it ships by
   default; otherwise expose it as opt-in.
6. Add unit + golden tests.
7. Update this document and the ADR if the addition introduces a new
   user-facing artefact type.
