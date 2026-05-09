# 06 — Application Services

This document describes the **application-service layer** — the use cases
and orchestration sagas that sit between the User Interaction adapter and
the domain core.

Application services are the *only* place where orchestration logic
lives. Aggregates and domain services know nothing about each other; the
application service composes them.

---

## 1. Layering recap

```
adapters/cli ──► application/services ──► domain/{aggregates,services}
                                          │
                                          ▼
                                       ports
                                          │
                                          ▼
                                       adapters/{llm,fs,kubernetes,…}
```

See [ADR-0014](../adr/0014-hexagonal-ports-and-adapters.md) for the
dependency rule. Application services depend on **ports**; the
composition root wires concrete adapters at startup.

---

## 2. Application services per bounded context

| Context                  | Service class                       | Responsibility                                                                 |
| ------------------------ | ----------------------------------- | ------------------------------------------------------------------------------ |
| Intent Interpretation    | `IntentInterpretationService`       | Parse `Intent` → `CodegenRequest`. Owns retry/back-off and demo fallback.      |
| API Modelling            | `ApiModellingService`               | Build `OpenAPIDocument` from `CodegenRequest`.                                 |
| Artifact Generation      | `ArtifactGenerationService`         | Run all selected generators against an IR. Produce an `ArtifactBundle`.        |
| Cluster Provisioning     | `ClusterProvisioningService`        | Ensure cluster, deploy CRD + instance, verify.                                 |
| User Interaction         | (each Click command)                | Bind CLI invocations to application services.                                   |
| Observability            | `EventDispatcher`                   | Subscribe to a `DomainEvent` stream and fan out to telemetry sinks.            |

The cross-cutting orchestrator:

| Service                          | Responsibility                                                                                                                        |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `GenerationOrchestrator` (Saga)  | Sequence the six contexts above through their stages. Listen for events, decide on recovery, run compensating actions on failure.    |

---

## 3. Use cases

The following use cases form the public surface of the application
layer. Each maps to a CLI command in
[`bounded-contexts/05-user-interaction.md`](bounded-contexts/05-user-interaction.md).

### 3.1 `GenerateFromIntent` *(primary)*

```python
class GenerateFromIntent:
    def __init__(
        self,
        orchestrator: GenerationOrchestrator,
        runs: RunRepository,
    ): ...

    def execute(self, params: GenerateParams) -> GenerationRun:
        """
        params.intent_text          — the user's natural-language description
        params.output_dir           — where artefacts land (default: ./generated_specs/<kind>)
        params.deploy_to_cluster    — bool; if False, stop after Persist
        params.cluster_name         — Kind cluster name; default "ai-platform-demo"
        params.allow_demo_mode      — bool; default True
        params.requested_generators — list of generators to run (default: CRD + Instance + OpenAPI)
        """
```

Stages run by the orchestrator:

1. **Interpret** — `IntentInterpretationService.parse(intent)`
2. **Model** — `ApiModellingService.build(request)`
3. **Generate** — `ArtifactGenerationService.generate(ir, output_dir, requested_generators)`
4. **Persist** — `ArtifactRepository.save(bundle)` (already happened inside Generate; this stage seals the manifest)
5. **Provision** *(optional)* — `ClusterProvisioningService.ensure(cluster_name)`, `deploy(bundle)`, `verify`
6. **Verify** — final `RunSucceeded` or `RunFailed`

### 3.2 `BuildFromRequestFile`

Skips the **Interpret** stage; reads a checked-in `CodegenRequest` from
disk and runs Model → Generate → Persist [→ Provision → Verify].

### 3.3 `ValidateRequest`

Runs only `IntentInterpretationService.validate(request)`; does not
generate. Useful in CI to gate PRs that change requests.

### 3.4 `ListExamples`

Returns the curated list of demo scenarios. Pure read, no side effects.

### 3.5 `EnsureCluster` / `TeardownCluster`

Standalone wrappers around `ClusterProvisioningService` for users who
just want the cluster lifecycle.

### 3.6 `DescribeRun`

Reads a `GenerationRun` by ID from `RunRepository` and returns its
current state.

---

## 4. The Generation Orchestrator (Saga)

```python
class GenerationOrchestrator:
    def __init__(
        self,
        interpret: IntentInterpretationService,
        model: ApiModellingService,
        generate: ArtifactGenerationService,
        provision: ClusterProvisioningService,
        runs: RunRepository,
        events: EventDispatcher,
        clock: Clock,
    ): ...

    def run(self, params: GenerateParams) -> GenerationRun:
        run = RunFactory.new(params)
        self.runs.append(run)
        self.events.publish(RunStarted(run.id, run.started_at))

        try:
            self._stage(run, "interpret",  lambda: self.interpret.parse(run.intent))
            self._stage(run, "model",      lambda: self.model.build(run.request))
            self._stage(run, "generate",   lambda: self.generate.run(run.ir, params))
            if params.deploy_to_cluster:
                self._stage(run, "provision", lambda: self.provision.ensure_and_deploy(run.bundle, params))
                self._stage(run, "verify",    lambda: self.provision.verify(run.deployment))
            self.events.publish(RunSucceeded(run.id, ...))
            return run.transition(succeeded=True)
        except PlatformGeneratorError as e:
            self._compensate(run, e)
            self.events.publish(RunFailed(run.id, error_code=e.code))
            raise
```

### 4.1 Stage decorator

`_stage` is the bookkeeping helper that:

1. Publishes `StageStarted(stage)`.
2. Times execution with the injected `Clock`.
3. On success: publishes `StageSucceeded(stage, duration_ms)`,
   transitions the run state.
4. On failure: publishes `StageFailed(stage, error_code, recoverable)`
   and re-raises.

### 4.2 Recovery rules

| Stage         | Error                                  | Recovery                                                                 |
| ------------- | -------------------------------------- | ------------------------------------------------------------------------ |
| Interpret     | `LlmRateLimited`                       | Retry up to 3 times with exponential backoff.                            |
| Interpret     | `LlmAuthenticationFailed` / `LlmUnavailable` | If `allow_demo_mode`, swap to `DemoModeLlmProvider` adapter and retry once. |
| Interpret     | `LlmResponseUnparseable`               | Retry once with a stricter system prompt; otherwise fail.                |
| Model         | any                                    | Terminal — the IR builder is pure.                                       |
| Generate      | `TemplateRenderingError`               | Terminal — bug in templates.                                              |
| Persist       | `ArtifactWriteFailed`                  | Compensate: delete partial bundle. Terminal.                              |
| Provision     | `PrerequisiteMissing`                  | Terminal with actionable error.                                          |
| Provision     | `ClusterCreationTimedOut`              | Compensate: `kind delete cluster`. Re-raise terminal.                    |
| Verify        | `DeploymentVerificationFailed`         | Compensate: emit diagnostic snapshot (events, describe). Terminal.       |

### 4.3 Compensating actions

- `delete_partial_bundle(run)` — removes the target dir if Persist fails.
- `delete_cluster(run)` — removes a half-created cluster.
- `emit_diagnostic_snapshot(run)` — captures `kubectl describe`,
  `kubectl get events`, `kubectl get crd ... -o yaml` for the user.

---

## 5. Public DTOs

The application layer exposes Pydantic DTOs at its public surface. CLI
adapters serialise them; tests rely on them.

```python
class GenerateParams(BaseModel):
    intent_text: str
    output_dir: Path | None = None
    deploy_to_cluster: bool = True
    cluster_name: str = "ai-platform-demo"
    allow_demo_mode: bool = True
    requested_generators: list[ArtifactType] = [
        ArtifactType.OPENAPI,
        ArtifactType.CRD,
        ArtifactType.INSTANCE,
    ]
    capture_prompts: bool = False  # see ADR-0020
    log_format: Literal["tty", "json", "quiet"] = "tty"
```

```python
class GenerationSummary(BaseModel):
    run_id: RunId
    state: RunState
    gvk: GVK
    bundle_dir: Path | None
    artefact_paths: list[Path]
    cluster_name: str | None
    deployment_status: str | None
    duration_ms: int
    provider_mode: ProviderMode
```

---

## 6. Service contracts (per context)

### 6.1 `IntentInterpretationService`

```python
class IntentInterpretationService:
    def parse(self, intent: Intent) -> CodegenRequest: ...
    def validate(self, request: CodegenRequest) -> list[FieldViolation]: ...
    def enhance(self, request: CodegenRequest) -> CodegenRequest: ...
```

Constructor injects: `LlmProvider`, `RequestValidator`, `RequestEnhancer`,
`EventDispatcher`, `Clock`.

### 6.2 `ApiModellingService`

```python
class ApiModellingService:
    def build(self, request: CodegenRequest) -> OpenAPIDocument: ...
```

Pure — no IO. Validates the produced IR with
`StructuralSchemaValidator` and raises `IRRejected`.

### 6.3 `ArtifactGenerationService`

```python
class ArtifactGenerationService:
    def run(
        self,
        ir: OpenAPIDocument,
        params: GenerateParams,
    ) -> ArtifactBundle: ...
```

Internally selects the right `ArtifactGenerator` instances, runs them
sequentially, computes provenance, and writes via `ArtifactRepository`.

### 6.4 `ClusterProvisioningService`

```python
class ClusterProvisioningService:
    def check_prerequisites(self) -> None: ...
    def ensure(self, cluster_name: str) -> Cluster: ...
    def deploy(self, bundle: ArtifactBundle, cluster: Cluster) -> Deployment: ...
    def verify(self, deployment: Deployment) -> Deployment: ...
    def teardown(self, cluster_name: str) -> None: ...
```

### 6.5 `EventDispatcher`

```python
class EventDispatcher:
    def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, predicate: Callable[[DomainEvent], bool], sink: TelemetrySink) -> None: ...
```

In production wired to a single `MultiSink` of `StructlogSink` +
optionally `OtelSink`. In tests wired to an in-memory `RecordingSink`
that supports `assert_events_in_order(...)`.

---

## 7. Composition root

`application/composition.py` is the only file that imports concrete
adapters. It is invoked once per process.

```python
def build_orchestrator(config: AppConfig) -> GenerationOrchestrator:
    clock        = SystemClock()
    secrets      = ChainSecretProvider([EnvSecretProvider(), DotenvSecretProvider() if config.load_env else None])
    llm_primary  = OpenRouterLlmAdapter(api_key=secrets["OPENROUTER_API_KEY"], model=config.model)
    llm          = FallbackLlmProvider(primary=llm_primary, fallback=DemoModeLlmAdapter())
    fs_repo      = FilesystemArtifactRepository(root=config.artifact_root)
    runs_repo    = JsonlRunRepository(path=config.runs_path)
    runtime      = KindClusterRuntime()
    sink         = MultiSink([StructlogSink(config.log_format), OtelSink() if config.otel_enabled else None])
    events       = EventDispatcher(default_sink=sink)

    return GenerationOrchestrator(
        interpret = IntentInterpretationService(llm, RequestValidator(), RequestEnhancer(), events, clock),
        model     = ApiModellingService(StructuralSchemaValidator(), events),
        generate  = ArtifactGenerationService(fs_repo, generators=default_generators(), events=events),
        provision = ClusterProvisioningService(runtime, events, clock),
        runs      = runs_repo,
        events    = events,
        clock     = clock,
    )
```

This keeps every concrete adapter discoverable in one place and makes
test wiring trivial — tests construct an orchestrator with stub adapters
directly.
