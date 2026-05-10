# ADR-0015: Template Method pattern for code generation

## Status

Accepted — 2025-05-09

## Context

We expect to grow many *artefact generators* over time: CRD YAML, sample
instance YAML, Go controller scaffold, MCP server, Helm chart, Kustomize
overlays, Terraform provider stub. Each generator shares a common skeleton:

1. Validate the OpenAPI IR satisfies its preconditions.
2. Resolve naming conventions (group, version, kind, file paths).
3. Render templates with the IR as context.
4. Post-process (e.g. format YAML, run `gofmt`).
5. Compute checksums and update the provenance manifest.
6. Emit `ArtifactGenerated` domain event.

Without a shared structure, each generator reimplements these steps and
they slowly drift apart.

## Decision

Every artefact generator extends an abstract `ArtifactGenerator` base class
implementing the **Template Method** pattern:

```python
class ArtifactGenerator(ABC):
    name: str

    def generate(self, ir: OpenAPIDocument, target: Path) -> ArtifactBundle:
        self._check_preconditions(ir)
        plan = self._plan(ir, target)
        outputs = self._render(plan)
        outputs = self._post_process(outputs)
        bundle = self._finalise(outputs, target)
        return bundle

    @abstractmethod
    def _check_preconditions(self, ir: OpenAPIDocument) -> None: ...
    @abstractmethod
    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan: ...
    @abstractmethod
    def _render(self, plan: GenerationPlan) -> list[RenderedFile]: ...
    def _post_process(self, files: list[RenderedFile]) -> list[RenderedFile]:
        return files  # default: no-op
    def _finalise(self, files: list[RenderedFile], target: Path) -> ArtifactBundle: ...
```

Concrete generators (`CrdYamlGenerator`, `InstanceYamlGenerator`,
`GoControllerGenerator`, `McpServerGenerator`, ...) only override the
abstract steps. Cross-cutting concerns (provenance, idempotency, telemetry,
formatting) live in the base class.

Templates use **Jinja2** with strict undefined-variable handling
(`StrictUndefined`) so missing fields fail loudly during testing.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Strategy pattern only | More flexible | Forces every generator to wire its own provenance/telemetry |
| Function-only generators | Simplest | No place to put shared lifecycle |
| Plugin discovery (entry points) | Extensibility | Premature; we have a small known set |
| Per-language template engines | Best fit per artefact | Operational cost of multiple engines outweighs marginal fidelity |

## Consequences

### Positive
- Adding a new artefact type is a tightly-bounded task.
- Cross-cutting policy (idempotency, provenance, gofmt, yamlfmt) is enforced
  in one place.
- Easy to write a single generic test suite that runs across all generators.

### Negative / Trade-offs
- Inheritance is sometimes harder to reason about than composition. We
  mitigate by making the base class small and pure.
- Generator authors must understand the lifecycle.

### Neutral
- Future generators can opt out of the base class by implementing the
  `ArtifactGenerator` Protocol directly, but this is discouraged in code
  review.

## Related Decisions

- ADR-0004: Adopt OpenAPI 3.0 as the canonical intermediate representation
- ADR-0005: Generate Kubernetes Custom Resource Definitions as primary output
- ADR-0011: Generate Go controllers using the kubebuilder scaffold pattern
- ADR-0013: Filesystem as the artifact store for generated specs
- ADR-0018: Test pyramid: unit / integration / e2e / golden-file
- DDD: `docs/ddd/bounded-contexts/03-artifact-generation.md`
