# ADR-0006: Use Kind for local Kubernetes cluster testing

## Status

Accepted — 2025-05-09

## Context

The Cluster Provisioning bounded context
(`docs/ddd/bounded-contexts/04-cluster-provisioning.md`) needs a Kubernetes
cluster against which to deploy and validate generated CRDs. The cluster
must be:

- Cheap to create (the demo aims for sub-three-minute end-to-end runs).
- Disposable (the demo creates and tears down clusters at will).
- Functionally equivalent to production Kubernetes (CRDs, controllers, API
  machinery all behave the same).
- Available on developer laptops and in CI without cloud credentials.

## Decision

We use **[Kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker)** as the
default cluster runtime for local development, demos, and CI. Specifically:

- The default cluster name is `ai-platform-demo`.
- A custom kubeconfig is written to `~/.kube/config-<cluster-name>` to avoid
  polluting the user's primary kubeconfig.
- Cluster lifecycle (create, deploy, verify, delete) is owned by
  `KindClusterManager` inside the Cluster Provisioning context.
- Cluster creation timeout is bounded at **300 seconds**; on timeout, the
  domain raises `ClusterProvisioningTimedOut` (see
  [ADR-0016](0016-validation-pipeline-error-model.md)).

Other Kubernetes runtimes (k3d, minikube, real EKS/GKE/AKS) are first-class
*adapters* behind a `ClusterRuntime` port (per
[ADR-0014](0014-hexagonal-ports-and-adapters.md)) and can be selected via
configuration. Only Kind ships in the default distribution.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| k3d | Faster start, lighter weight | Less broadly known; smaller ecosystem |
| minikube | Familiar to many users | Heavier (full VM by default); slower |
| Cloud cluster (EKS/GKE/AKS) | Production-faithful | Requires credentials; expensive; slow to provision |
| In-process apiserver (envtest) | Very fast | Not a real cluster — cannot exercise admission, networking, controllers |

## Consequences

### Positive
- Sub-minute cluster creation on a warm Docker daemon.
- Identical API surface to production Kubernetes.
- Multi-node clusters available for HA / topology testing.
- The `run.sh demo` flow is fully self-contained.

### Negative / Trade-offs
- Requires a running Docker daemon. We surface this as a prerequisite check
  with an actionable error message.
- macOS / Windows performance is bound by the Docker VM's networking.

### Neutral
- Kind is upstream-maintained by SIG-Testing; we track its release cadence
  and pin a minimum version in `requirements.txt` (or a tools manifest).

## Related Decisions

- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0016: Validation pipeline with explicit error model
- ADR-0017: Observability and telemetry strategy
- DDD: `docs/ddd/bounded-contexts/04-cluster-provisioning.md`
