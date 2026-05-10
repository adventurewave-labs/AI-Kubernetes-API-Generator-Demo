# ADR-0005: Generate Kubernetes Custom Resource Definitions as primary output

## Status

Accepted — 2025-05-09

## Context

The product mission (see `docs/ddd/01-domain-vision.md`) is to compress the
time between *"I have an idea for a platform API"* and *"That API is running
in a Kubernetes cluster"*. The Kubernetes-native way to express a new API is
a **Custom Resource Definition (CRD)** plus, optionally, a controller to
reconcile its instances.

We could in principle target other API surfaces — Helm charts, Crossplane
compositions, Terraform providers, plain REST microservices — but each
shifts the centre of gravity away from the Kubernetes-native flow our users
already operate in.

## Decision

The **primary output** of the system is a pair of YAML documents:

1. A Kubernetes `CustomResourceDefinition` (`apiextensions.k8s.io/v1`).
2. A sample custom resource instance valid against that CRD.

Both are derived from the OpenAPI IR (see
[ADR-0004](0004-openapi-3-as-intermediate-representation.md)). Other
artefact types (Go controllers, MCP servers, Helm charts, GitOps overlays)
are *secondary* outputs produced by additional generators that consume the
same IR.

The generator enforces these CRD invariants:

- Group is reverse-DNS (validated against `^[a-z0-9.-]+\.[a-z0-9.-]+$`).
- Version follows `v[0-9]+(alpha|beta)?[0-9]*` (e.g. `v1alpha1`, `v1beta2`,
  `v1`).
- Kind is CamelCase (`^[A-Z][a-zA-Z0-9]*$`).
- The CRD declares `served: true` and `storage: true` on the version it ships.
- The schema enables structural validation (`x-kubernetes-preserve-unknown-fields`
  is not set unless explicitly requested).

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| Crossplane Compositions | Higher-level platform abstraction | Re-targetable later; CRD is the foundation Crossplane itself uses |
| Helm chart only | Familiar packaging | Helm describes deployment, not API shape |
| Plain OpenAPI + REST scaffold | Provider-neutral | Misses the K8s-native ecosystem entirely |
| Terraform provider | IaC reach | Wrong abstraction — providers wrap APIs, they do not define them |

## Consequences

### Positive
- Output is immediately usable with `kubectl apply` and `kind`.
- Maps cleanly onto the controller-runtime / Operator SDK ecosystem.
- Compatible with GitOps tools (Argo CD, Flux) without further translation.

### Negative / Trade-offs
- We inherit Kubernetes' versioning constraints (alpha → beta → ga
  promotion, conversion webhooks for v2+).
- CRD validation is a subset of OpenAPI; the generator must reject
  unrepresentable schemas at the *Validation* stage rather than at deploy
  time.

### Neutral
- The CRD serves as the *source of truth* for downstream secondary outputs
  such as Go types and clientsets.

## Related Decisions

- ADR-0004: Adopt OpenAPI 3.0 as the canonical intermediate representation
- ADR-0006: Use Kind for local Kubernetes cluster testing
- ADR-0011: Generate Go controllers using the kubebuilder scaffold pattern
- DDD: `docs/ddd/bounded-contexts/03-artifact-generation.md`
