# ADR-0011: Generate Go controllers using the kubebuilder scaffold pattern

## Status

Accepted — 2025-05-09

## Context

For a CRD to do anything beyond storing structured YAML, it usually needs a
*controller* that reconciles desired state with actual state. In the
Kubernetes ecosystem there are three dominant ways to write controllers:

- **kubebuilder** (and Operator SDK on top of it) — Go, controller-runtime,
  the de-facto standard.
- **kopf** — Python, lower learning curve, smaller community.
- **Metacontroller / shell scripts** — quick but limited.

Our generated controllers are scaffolds — users will own them long-term. We
should generate code that aligns with what the broader ecosystem expects,
so users can extend it with familiar tools (`make`, `controller-gen`,
`kustomize`).

## Decision

We generate Go controller scaffolds that follow the
**[kubebuilder](https://book.kubebuilder.io/) project layout**:

```
<output_dir>/
├── main.go
├── api/
│   └── <version>/
│       └── <kind>_types.go
├── internal/
│   └── controller/
│       └── <kind>_controller.go
├── Dockerfile
├── go.mod
└── (placeholder kubebuilder markers)
```

- Types use the `metav1.TypeMeta` / `metav1.ObjectMeta` embedding pattern
  with `Spec` and `Status` sub-types.
- Reconcilers embed `client.Client` and `runtime.Scheme`.
- RBAC kubebuilder markers are emitted alongside the reconciler.
- The `Dockerfile` is a multi-stage build using `gcr.io/distroless/static`
  for the runtime image (non-root user `65532:65532`).
- Pinned dependency versions live in `go.mod` and are kept current via
  Renovate / Dependabot configuration in the generator repository.

The generator does **not** invoke `controller-gen`, `kustomize`, or `go mod
tidy` itself. The scaffold ships with a `Makefile` (added in
implementation) that performs those steps in the user's environment.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Operator SDK | Higher level | Builds on kubebuilder; adds another tool to the chain |
| kopf (Python) | Same language as generator | Smaller community; users would expect Go in production |
| Metacontroller hooks | Lightweight | Limited expressiveness; not idiomatic for new APIs |
| No controller — CRD only | Simpler | Users almost always need reconciliation logic eventually |

## Consequences

### Positive
- Generated code is immediately recognisable to Kubernetes engineers.
- Compatible with `make manifests`, `make generate`, `make docker-build`.
- Clean migration path to Operator SDK if the user prefers it.

### Negative / Trade-offs
- Maintaining the Go templates means tracking upstream kubebuilder
  layout/marker changes.
- Users who do not know Go inherit a Go codebase. Documentation must call
  this out clearly.

### Neutral
- The Go scaffold is one of several optional secondary outputs (see
  [ADR-0005](0005-kubernetes-crd-as-primary-output.md)). It is not produced
  unless requested.

## Related Decisions

- ADR-0004: Adopt OpenAPI 3.0 as the canonical intermediate representation
- ADR-0005: Generate Kubernetes Custom Resource Definitions as primary output
- ADR-0015: Template Method pattern for code generation
- DDD: `docs/ddd/bounded-contexts/03-artifact-generation.md`
