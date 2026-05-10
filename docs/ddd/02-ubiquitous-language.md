# 02 — Ubiquitous Language

This is the canonical glossary for the AI Kubernetes API Generator. **The
exact terms here are used in code, tests, log lines, commit messages, and
product copy.** Synonyms are listed where they exist; the *preferred* form
is bolded.

When a new concept is introduced in a pull request, this document **must**
be updated in the same PR. Contradictions between code and this document
are bugs in the code, not the document.

---

## Top-level concepts

| Term | Definition |
| --- | --- |
| **Codegen Request** | A structured, validated representation of *what the user wants*. The output of the Intent Interpretation context and the input to API Modelling. Has fields: `group`, `version`, `kind`, `spec_properties`, `output_dir`, `description`. |
| **Intent** | The user's natural-language description before parsing. A free-text value object passed in by the User Interaction context. |
| **OpenAPI IR** (Intermediate Representation) | An OpenAPI 3.0 document that is the canonical hand-off between API Modelling and Artifact Generation. See [ADR-0004](../adr/0004-openapi-3-as-intermediate-representation.md). |
| **Artifact** | Any file produced by the system: CRD manifest, sample instance, OpenAPI document, Go controller file, MCP server file, manifest.json. |
| **Artifact Bundle** | The set of artifacts produced by a single generation run, bound together by a single `manifest.json`. |
| **Provenance Manifest** | The `manifest.json` written alongside artefacts; records tool version, model, mode, timestamp, and SHA-256 of every artefact. |
| **Generation Run** | One end-to-end execution of the system from intent to artefact bundle. Has an ID. |

## Identity / naming

| Term | Definition |
| --- | --- |
| **Group** | The reverse-DNS name that namespaces a CRD's API (`database.cnoe.io`). Validated against `^[a-z0-9.-]+\.[a-z0-9.-]+$`. Value object. |
| **Version** | The API version of a CRD (`v1alpha1`, `v1beta2`, `v1`). Value object. |
| **Kind** | The CamelCase name of a custom resource (`PostgresCluster`, `VectorDB`). Validated against `^[A-Z][a-zA-Z0-9]*$`. Value object. |
| **GVK** | Group + Version + Kind. The minimal triple that uniquely identifies a Kubernetes resource type. Value object. |
| **Resource Plural** | The lowercase plural form of `Kind` (`postgresclusters`). Derived; not stored. |
| **Singular Name** | The lowercase singular form of `Kind` (`postgrescluster`). Derived. |

## API shape

| Term | Definition |
| --- | --- |
| **Spec Property** | A named field of the resource's `.spec`, with a JSON-schema type and an optional description. Value object: `(name, type, description, constraints)`. |
| **Spec Schema** | The JSON-schema object describing the union of all `Spec Property`s of a `Kind`. |
| **Status Schema** | The JSON-schema for the resource's observed state. Generator-emitted skeleton; user-owned. |
| **Field Violation** | A typed validation failure: `(path, expected, actual, message)`. See [ADR-0016](../adr/0016-validation-pipeline-error-model.md). |
| **Structural Schema** | A CRD schema that satisfies Kubernetes' [structural-schema rules](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#specifying-a-structural-schema). The generator emits only structural schemas by default. |

## LLM and demo-mode

| Term | Definition |
| --- | --- |
| **LLM Provider** | An adapter implementing the `LlmProvider` port. Concrete implementations: OpenRouter, OpenAI, Demo Mode, Fake (test). |
| **Provider Mode** | One of `live` or `demo`. Captured in the provenance manifest. |
| **Demo Mode** | A deterministic in-process implementation of `LlmProvider` that returns a curated `CodegenRequest` based on keyword matching. See [ADR-0009](../adr/0009-graceful-degradation-to-demo-mode.md). |
| **Demo Scenario** | A named entry in the Demo Mode catalogue (`postgres-cluster`, `redis-cluster`, `vector-db`, `notebook`, …). |
| **System Prompt** | The instructions sent ahead of every user message that constrain the LLM's response shape. Owned by the Intent Interpretation context. |
| **Structured Output** | Output emitted by the LLM in JSON form, parsed into a `CodegenRequest`. The system relies on the provider's JSON-mode where available. |

## Cluster

| Term | Definition |
| --- | --- |
| **Cluster Runtime** | An adapter implementing the `ClusterRuntime` port. Default: `kind`. |
| **Cluster** | A live Kubernetes cluster managed by the system. Has a name, a kubeconfig path, and a status. |
| **Deployment** | The act of applying a CRD and a sample instance to a Cluster, plus the resulting state. |
| **Verification** | The act of confirming a deployed CRD is `Established` and a deployed instance is retrievable via `kubectl get`. |
| **Prerequisite** | An external tool whose presence is required (`docker`, `kind`, `kubectl`). |

## Generation

| Term | Definition |
| --- | --- |
| **Artifact Generator** | A class that consumes the OpenAPI IR and produces one or more Artifacts. Implements the Template Method pattern from [ADR-0015](../adr/0015-template-method-for-code-generation.md). |
| **Generation Plan** | The intermediate, side-effect-free description of *what files would be written* before any IO occurs. |
| **Rendered File** | A `(path, bytes, mode)` triple, the output of a generator's `_render` step. |
| **Post-processing** | Generator-specific normalisation (e.g. `gofmt`, `yamlfmt`) applied after rendering. |
| **Idempotency** | The property that re-running a generator with the same input produces byte-identical output (modulo timestamps recorded in `manifest.json`). |

## Lifecycle

| Term | Definition |
| --- | --- |
| **Generation Orchestrator** | The application service / saga that drives a Generation Run end-to-end. |
| **Saga** | A long-running orchestration with explicit compensating actions on failure. The Generation Orchestrator is a saga. |
| **Compensating Action** | An action that undoes a previously successful step when a later step fails (e.g. delete a partially-written artefact bundle). |
| **Stage** | A discrete phase of a Generation Run: `Interpret`, `Model`, `Generate`, `Persist`, `Provision`, `Verify`. |

## Errors

| Term | Definition |
| --- | --- |
| **Domain Validation Error** | A typed exception class carrying a list of `Field Violation`s. |
| **Recoverable Error** | An error the orchestrator may retry or work around (rate limits, demo-mode fallback). |
| **Terminal Error** | An error that aborts the Generation Run. |
| **Error Code** | A stable, machine-readable string identifier for an error class (`E_INTENT_LLM_UNAVAILABLE`). |

## Observability

| Term | Definition |
| --- | --- |
| **Domain Event** | An immutable record of something the domain considers significant (`CodegenRequestParsed`, `ArtifactGenerated`, `ClusterDeploymentSucceeded`). |
| **Telemetry Sink** | An adapter implementing the `TelemetrySink` port: structlog, OTEL, noop, or a composite. |
| **Span** | An OpenTelemetry span. One per stage at minimum; nested for sub-operations. |
| **Provenance** | The audit trail of *how* an artifact bundle came to exist: tool version, model, mode, prompts, timestamps. |

## CLI / interaction

| Term | Definition |
| --- | --- |
| **Command** | A top-level CLI verb (`generate`, `interactive`, `build`, `examples`, `cluster`, `validate`). |
| **Interactive Session** | A REPL-like mode where the user chains multiple Generation Runs with shared configuration. |
| **Renderer** | The component that turns Domain Events into terminal output. Two implementations: `RichRenderer` (TTY) and `JsonRenderer` (CI). |

---

## Forbidden synonyms

These words are *not* used in this codebase, even though they appear in
adjacent ecosystems. They are forbidden because they imply something
different from our intent.

| Forbidden | Use instead | Reason |
| --- | --- | --- |
| "schema definition" | **Spec Schema** / **Structural Schema** | Kubernetes uses both "schema" and "schema definition" inconsistently — we always disambiguate. |
| "model" (for LLM) | **LLM Provider Model** | "Model" alone collides with our domain models (Pydantic). |
| "agent" (for the AI provider) | **LLM Provider** | Reserves "agent" for application services in the multi-agent architecture ([ADR-0010](../adr/0010-multi-agent-layered-architecture.md)). |
| "config" (for `CodegenRequest`) | **Codegen Request** | Reserves "config" for tool configuration. |
| "result" (for an Artifact Bundle) | **Artifact Bundle** | Disambiguates from `GenerationResult` data class. |
| "spec" alone | **Spec Schema** or **Spec Property** | "Spec" is overloaded between Kubernetes (`.spec`) and the resource specification. |
