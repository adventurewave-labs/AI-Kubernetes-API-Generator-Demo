# 07 — Anti-Corruption Layers

This document describes how the AI Kubernetes API Generator integrates
with external systems without letting their models leak into the domain
core. Every external integration is mediated by a **port** (an abstract
interface in domain language) and one or more **adapters** (concrete
implementations).

The decision to layer this way is captured in
[ADR-0014](../adr/0014-hexagonal-ports-and-adapters.md). The list of
external systems is taken from the Strategic Design's "Generic"
subdomains in [`03-strategic-design.md`](03-strategic-design.md).

---

## 1. Ports overview

| Port                       | Purpose                                                          | Owner context           |
| -------------------------- | ---------------------------------------------------------------- | ----------------------- |
| `LlmProvider`              | Translate `Intent` + system prompt → JSON response               | Intent Interpretation   |
| `ArtifactRepository`       | Persist and retrieve `ArtifactBundle`s                           | Artifact Generation     |
| `ClusterRuntime`           | Lifecycle of a Kubernetes cluster + apply/get manifests          | Cluster Provisioning    |
| `SecretProvider`           | Resolve named secrets                                            | All (cross-cutting)     |
| `TelemetrySink`            | Receive `DomainEvent`s and translate to logs/metrics/traces      | Observability           |
| `Clock`                    | Provide the current time (testable)                               | All                     |
| `RunRepository`            | Append + retrieve `GenerationRun` entities                        | Orchestrator            |

---

## 2. `LlmProvider`

### 2.1 Port

```python
class LlmProvider(Protocol):
    name: str
    model: str
    mode: ProviderMode

    def is_available(self) -> bool: ...
    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None = None,
        timeout_s: float = 60.0,
    ) -> JsonObject: ...
```

The port is **JSON-shaped** on purpose. Domain code never sees a `dict`
that hasn't been validated against a Pydantic schema; it sees a
`CodegenRequest` factory output.

### 2.2 Adapters

| Adapter                  | Backend                                | Notes                                                                                                                  |
| ------------------------ | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `OpenRouterLlmAdapter`   | `openai` SDK pointed at OpenRouter     | Uses provider-native JSON mode if available; gracefully falls back to "extract last code block" parsing on older models. |
| `OpenAiLlmAdapter`       | `openai` SDK pointed at OpenAI         | Adds `response_format={"type": "json_schema", ...}` when given a schema.                                                |
| `OllamaLlmAdapter`       | Local Ollama HTTP API                  | Optional; outside the default install. Useful for air-gapped use.                                                       |
| `DemoModeLlmAdapter`     | In-process keyword-keyed catalogue     | See [ADR-0009](../adr/0009-graceful-degradation-to-demo-mode.md).                                                       |
| `FakeLlmAdapter`         | Deterministic in-memory               | Test only.                                                                                                              |
| `FallbackLlmProvider`    | Composite                              | Wraps a primary and a fallback; swaps to fallback on `LlmUnavailable` / `LlmAuthenticationFailed`.                     |

### 2.3 Translation responsibilities (the "anti-corruption" part)

The adapter must:

1. Translate the provider's exception types into our error taxonomy
   ([ADR-0016](../adr/0016-validation-pipeline-error-model.md)). Substring
   matching on error messages is **forbidden** outside the adapter.
2. Translate provider-specific JSON-mode flags into our uniform
   `complete_json` interface.
3. Strip non-JSON content (preambles, code fences) before returning.
4. Enforce the timeout uniformly (some SDKs ignore the parameter; we
   wrap the call in `asyncio.wait_for` or a thread guard).

### 2.4 Forbidden leakage

Domain code may **not** import:

- `openai`, `anthropic`, `httpx` (except in adapters).
- Any provider-specific exception class.
- Any provider-specific request/response model.

`mypy --strict` catches violations through `__all__` exports.

---

## 3. `ArtifactRepository`

### 3.1 Port

```python
class ArtifactRepository(Protocol):
    def save(self, bundle: ArtifactBundle) -> None: ...
    def load(self, run_id: RunId) -> ArtifactBundle: ...
    def exists(self, run_id: RunId) -> bool: ...
```

### 3.2 Adapters

| Adapter                          | Backend                                                         | Notes                                                              |
| -------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------ |
| `FilesystemArtifactRepository`   | Local filesystem under a configured root                       | Default. See [ADR-0013](../adr/0013-filesystem-as-artifact-store.md). |
| `GitArtifactRepository`          | Local git repo + auto-commit + optional `git push`             | Future. Treats each bundle as a commit.                            |
| `S3ArtifactRepository`           | AWS S3 (or S3-compatible)                                       | Future.                                                             |
| `OciArtifactRepository`          | OCI registry (artefact mediatype)                                | Future.                                                             |
| `InMemoryArtifactRepository`     | `dict[RunId, ArtifactBundle]`                                   | Test only.                                                          |

### 3.3 Path-safety responsibilities

The Filesystem adapter must:

- Resolve every output path with `Path.resolve()` and assert it is a
  child of the configured root before any write.
- Reject paths whose components contain `..` or symlinks pointing
  outside the root.
- Set explicit file modes (`0o644` for artefacts, `0o600` for
  manifests).

These guardrails are part of the security commitments in
[ADR-0020](../adr/0020-security-threat-model-and-hardening.md).

---

## 4. `ClusterRuntime`

### 4.1 Port

```python
class ClusterRuntime(Protocol):
    name: str  # "kind", "k3d", "external", ...

    def check_prerequisites(self) -> list[MissingTool]: ...
    def cluster_status(self, name: str) -> ClusterStatus: ...
    def create_cluster(self, name: str, config: ClusterConfig) -> Cluster: ...
    def delete_cluster(self, name: str) -> None: ...
    def apply(self, cluster: Cluster, manifest_path: Path) -> ApplyResult: ...
    def get(self, cluster: Cluster, gvk: GVK, name: str, namespace: str | None) -> ResourceState: ...
    def describe(self, cluster: Cluster, gvk: GVK, name: str, namespace: str | None) -> ResourceDescription: ...
    def events(self, cluster: Cluster) -> list[ClusterEvent]: ...
```

### 4.2 Adapters

| Adapter                       | Backend                                | Notes                                                              |
| ----------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| `KindClusterRuntime`          | `kind` + `kubectl` subprocesses        | Default. See [ADR-0006](../adr/0006-kind-for-local-cluster-testing.md). |
| `K3dClusterRuntime`           | `k3d` + `kubectl`                       | Optional.                                                          |
| `ExternalClusterRuntime`      | Pre-provisioned cluster, kubeconfig path provided | Skips creation; only applies and verifies.                         |
| `FakeClusterRuntime`          | In-memory state machine                 | Test only.                                                         |

### 4.3 Subprocess hygiene

All adapters must:

- Use `subprocess.run(..., shell=False, check=False, timeout=...)`.
- Never construct argv via string concatenation.
- Translate non-zero exit codes into typed
  `ClusterProvisioningError`s with the original stderr captured (and
  redacted) on the error.

---

## 5. `SecretProvider`

### 5.1 Port

```python
class SecretProvider(Protocol):
    def get(self, name: str) -> str | None: ...
    def names(self) -> list[str]: ...
```

### 5.2 Adapters

| Adapter                | Backend                              |
| ---------------------- | ------------------------------------ |
| `EnvSecretProvider`    | `os.environ`                         |
| `DotenvSecretProvider` | `.env` file via `python-dotenv`     |
| `KeyringProvider`      | OS keychain / Windows Credentials    |
| `VaultSecretProvider`  | HashiCorp Vault                      |
| `K8sSecretProvider`    | Mounted Kubernetes secret directory  |
| `ChainSecretProvider`  | Composite — first-hit wins           |

`ChainSecretProvider` is the default in `composition.py`.

---

## 6. `TelemetrySink`

### 6.1 Port

```python
class TelemetrySink(Protocol):
    def emit(self, event: DomainEvent) -> None: ...
    def flush(self) -> None: ...
```

### 6.2 Adapters

| Adapter           | Backend                       | Notes                                                           |
| ----------------- | ----------------------------- | --------------------------------------------------------------- |
| `StructlogSink`   | structlog                     | Default. Renders TTY (Rich) or JSON.                            |
| `OtelSink`        | OpenTelemetry SDK             | Opt-in. Spans + metrics + log records.                          |
| `RecordingSink`   | In-memory list                | Test fixture.                                                   |
| `MultiSink`       | Composite                     | Fans events out to N sinks.                                     |
| `NoopSink`        | Drops everything              | `--quiet` mode.                                                 |

### 6.3 Redaction

All sinks pass payloads through `SecretRedactor` before emitting (see
[ADR-0017](../adr/0017-observability-and-telemetry.md)).

---

## 7. `Clock`

### 7.1 Port

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
```

### 7.2 Adapters

| Adapter        | Notes                       |
| -------------- | --------------------------- |
| `SystemClock`  | Default; UTC.               |
| `FrozenClock`  | Test only; advances on demand. |

The `Clock` port exists so that golden tests do not depend on wall time
([ADR-0018](../adr/0018-test-pyramid-strategy.md)).

---

## 8. `RunRepository`

### 8.1 Port

See [`04-tactical-design.md §6.2`](04-tactical-design.md#62-runrepository).

### 8.2 Adapters

| Adapter             | Backend                        |
| ------------------- | ------------------------------ |
| `JsonlRunRepository` | append-only JSONL file        |
| `SqliteRunRepository` | local SQLite DB              |
| `InMemoryRunRepository` | dict — test only             |

---

## 9. Cross-cutting rules for adapters

1. **Adapters never reach into the domain layer beyond their port.** A
   filesystem adapter must not import `OpenAPIDocument`; it sees only
   `ArtifactBundle`.
2. **Adapters log via the `TelemetrySink`**, not `print` or `logging`.
3. **Adapters declare their failure modes** via the typed exception
   hierarchy ([ADR-0016](../adr/0016-validation-pipeline-error-model.md)).
   They do **not** raise raw `Exception`.
4. **Adapters are tested** in the Integration tier
   ([ADR-0018](../adr/0018-test-pyramid-strategy.md)) against either the
   real backend (gated) or a high-fidelity fake.

---

## 10. New-adapter checklist

When adding an adapter (e.g. an `AnthropicLlmAdapter`):

- [ ] Declare the adapter class in `adapters/<port>/<vendor>.py`.
- [ ] Translate every vendor-specific exception into our taxonomy.
- [ ] Pass timeouts and respect cancellation.
- [ ] Redact secrets before logging.
- [ ] Add at least one integration test gated behind a real-credentials
      flag.
- [ ] Add a fake / contract test that runs in unit-test CI.
- [ ] Update `composition.py` with the new option.
- [ ] Update [`02-ubiquitous-language.md`](02-ubiquitous-language.md) if
      the adapter introduces new domain vocabulary.
- [ ] If the integration is a first-class user-facing choice, write an
      ADR.
