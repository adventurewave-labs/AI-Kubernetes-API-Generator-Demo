# Bounded Context — Cluster Provisioning

> **Purpose:** stand up (or attach to) a Kubernetes cluster, deploy the
> generated CRD and sample instance, and verify that the resulting custom
> resource is queryable.

This is a **supporting** subdomain. The "real" engineering value lives in
upstream contexts; this context is responsible for *closing the loop* so
the user sees their idea running.

---

## 1. Responsibilities

1. Check prerequisites (`docker`, `kind`, `kubectl`) and report the
   actionable result.
2. Ensure a cluster exists with the requested name, creating one if
   absent.
3. Apply the generated CRD and sample instance, in the right order, with
   appropriate waits.
4. Verify by re-reading the CRD's `Established` condition and the
   instance via `kubectl get`.
5. Tear down clusters on demand and on compensating-action paths.
6. Surface low-level errors as typed domain errors.

This context **does not**:

- Generate any artefact (Artifact Generation does that).
- Watch resources continuously (that's the user's controller's job).
- Manage non-Kubernetes infrastructure.

## 2. Ubiquitous language

Originated here: **Cluster**, **Cluster Runtime**, **Deployment**,
**Verification**, **Prerequisite**.

## 3. Aggregates and entities

| Type                  | Pattern         | Notes                                                                        |
| --------------------- | --------------- | ---------------------------------------------------------------------------- |
| `Cluster`             | Entity (root)   | See `../04-tactical-design.md §3.2`.                                        |
| `Deployment`          | Entity          | See `../04-tactical-design.md §3.3`. Belongs to a `Cluster`.                |
| `ClusterStatus`       | Value object    | `(exists, running, nodes, kubectl_accessible)`.                             |
| `DeploymentStatus`    | Value object    | `(crd_applied, instance_applied, resource_accessible, status_text?)`.       |
| `ClusterConfig`       | Value object    | `(name, runtime, node_count, port_mappings)`.                               |
| `MissingTool`         | Value object    | `(name, expected_version_range, install_hint)`.                             |

## 4. Domain services

| Service                       | Responsibility                                                              |
| ----------------------------- | --------------------------------------------------------------------------- |
| `PrerequisiteChecker`         | Inspect the OS and report missing tools.                                    |
| `ClusterLifecycleService`     | Create, delete, query clusters.                                              |
| `DeploymentService`           | Apply CRD, wait for `Established`, apply instance, wait for accessibility. |
| `DeploymentVerifier`          | Run `kubectl get` and `kubectl describe`; parse status.                    |
| `DiagnosticCollector`         | On verification failure, gather `kubectl get events` + describe output.    |

## 5. Application service

`ClusterProvisioningService`:

```python
def check_prerequisites(self) -> None: ...
def ensure(self, cluster_name: str) -> Cluster: ...
def deploy(self, bundle: ArtifactBundle, cluster: Cluster) -> Deployment: ...
def verify(self, deployment: Deployment) -> Deployment: ...
def teardown(self, cluster_name: str) -> None: ...
```

The orchestrator composes these.

## 6. Cluster lifecycle

### 6.1 Cluster creation (Kind default)

Default config (per [ADR-0006](../../adr/0006-kind-for-local-cluster-testing.md)):

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - { containerPort: 80,  hostPort: 80,  protocol: TCP }
      - { containerPort: 443, hostPort: 443, protocol: TCP }
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
```

The kubeconfig is written to `~/.kube/config-<cluster-name>` to keep the
user's primary kubeconfig clean. The context name is `kind-<cluster-name>`.

Creation timeout is 300 seconds. On timeout the service emits
`ClusterCreationFailed` with `error_code = E_CLUSTER_TIMEOUT` and
attempts a `kind delete cluster --name <name>` compensating action.

### 6.2 Deployment

Order matters:

1. Apply CRD.
2. Wait for the CRD's `Established` condition (poll `kubectl get crd
   <name> -o jsonpath="{.status.conditions[?(@.type=='Established')].status}"`
   with a 30-second budget).
3. Apply sample instance.
4. Wait for `kubectl get <kind> <name>` to return successfully (15 seconds).

### 6.3 Verification

`DeploymentVerifier` returns a `DeploymentStatus`. Failure modes:

- CRD missing → `E_CLUSTER_CRD_NOT_FOUND`.
- CRD not Established within budget → `E_CLUSTER_CRD_NOT_ESTABLISHED`.
- Instance not retrievable → `E_CLUSTER_INSTANCE_NOT_FOUND`.

On any of the above, `DiagnosticCollector` emits a structured event
containing `kubectl describe` and `kubectl get events` so the user sees
why.

## 7. Subprocess hygiene

All `kind` / `kubectl` / `docker` invocations:

- Use `subprocess.run(argv, shell=False, check=False, timeout=N)`.
- Pass `KUBECONFIG=~/.kube/config-<name>` explicitly when relevant.
- Capture both stdout and stderr.
- Translate non-zero exit codes via `ErrorTranslator` into typed errors.
- Are wrapped by an OTEL span when OTEL is enabled.

Per [ADR-0020](../../adr/0020-security-threat-model-and-hardening.md),
argv lists are constructed from validated value objects only — no string
formatting against user input.

## 8. Domain events emitted

| Event                          | When                                                              |
| ------------------------------ | ----------------------------------------------------------------- |
| `PrerequisiteCheckSucceeded`   | All required tools present.                                       |
| `PrerequisiteCheckFailed`      | One or more tools missing.                                        |
| `ClusterCreationStarted`       | Before `kind create cluster`.                                      |
| `ClusterCreationSucceeded`     | After `kubectl get nodes` returns within budget.                  |
| `ClusterCreationFailed`        | On any failure or timeout.                                        |
| `CrdApplied`                   | After CRD applied and Established.                                |
| `InstanceApplied`              | After sample instance applied.                                    |
| `DeploymentVerified`           | After `kubectl get` confirms.                                     |
| `DeploymentVerificationFailed` | On any verification failure (with `error_code`).                  |

## 9. Failure modes and recovery

| Failure                          | Recovery                                                                 |
| -------------------------------- | ------------------------------------------------------------------------ |
| `PrerequisiteMissing`            | Terminal with actionable install hints in `MissingTool.install_hint`.   |
| `ClusterCreationTimedOut`        | Compensating: `kind delete cluster`. Re-raise terminal.                  |
| `KubectlInvocationFailed`        | Terminal — captures stderr.                                              |
| `CrdNotEstablished`              | Compensating: `kubectl describe` for diagnostics. Terminal.              |
| `DeploymentVerificationFailed`   | Compensating: emit diagnostic snapshot. Terminal.                        |

## 10. Public contract

Inputs:

- `ArtifactBundle` (with at least a CRD + Instance).
- `cluster_name: str`.

Outputs:

- `Cluster` and `Deployment` entities.
- `DeploymentStatus`.

Errors:

- `ClusterProvisioningError` and subclasses
  ([ADR-0016](../../adr/0016-validation-pipeline-error-model.md)).

## 11. Testing strategy

- **Unit:** services with `FakeClusterRuntime`. Coverage target ≥ 90 %.
- **Integration:** `KindClusterRuntime` exercised against a real `kind`
  binary (gated behind `--run-cluster-tests`).
- **E2E:** the `./run.sh demo` script, gated to nightly CI
  ([ADR-0018](../../adr/0018-test-pyramid-strategy.md)).
- **Resilience:** simulate `kubectl apply` returning non-zero with various
  stderrs; assert correct error translation.

## 12. Future work

- Pluggable runtimes (k3d, external).
- Multi-cluster deployments.
- Bring-your-own-cluster mode (skip creation, kubeconfig path provided).
- Helm-based install of operator dependencies (cert-manager, ingress).
