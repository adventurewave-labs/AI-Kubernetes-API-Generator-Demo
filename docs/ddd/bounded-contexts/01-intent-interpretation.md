# Bounded Context — Intent Interpretation

> **Purpose:** translate a free-form natural-language **Intent** from a user
> into a validated, structured **`CodegenRequest`** aggregate that the rest
> of the system can rely on.

This is one of the two **core** subdomains of the system (the other is API
Modelling). The quality of every downstream artefact is gated on the
correctness and reliability of this context.

Strategic position: see [`../03-strategic-design.md`](../03-strategic-design.md).
Tactical building blocks: see [`../04-tactical-design.md`](../04-tactical-design.md).

---

## 1. Responsibilities

1. Accept an `Intent` (raw user text) and a configuration (target group,
   defaults, allowed providers).
2. Construct a system prompt that constrains the LLM to emit a JSON object
   with a known shape.
3. Invoke an `LlmProvider` to obtain a JSON response.
4. Parse, validate, and enhance the response into a `CodegenRequest`
   aggregate.
5. Decide when to retry, back off, or fall back to **Demo Mode**.
6. Emit the appropriate domain events
   ([`../05-domain-events.md`](../05-domain-events.md)).

This context **does not**:

- Build the OpenAPI IR (that's API Modelling).
- Render any artefact.
- Talk to any cluster.
- Render anything to the terminal.

## 2. Ubiquitous language inside this context

(See the canonical glossary in [`../02-ubiquitous-language.md`](../02-ubiquitous-language.md).)

The terms that *originate* here are: **Intent**, **System Prompt**,
**Structured Output**, **LLM Provider**, **Provider Mode**, **Demo Mode**,
**Demo Scenario**.

## 3. Aggregates and value objects

| Type                | Pattern         | Notes                                                                        |
| ------------------- | --------------- | ---------------------------------------------------------------------------- |
| `CodegenRequest`    | Aggregate root  | The output of this context. See `../04-tactical-design.md §4.1`.            |
| `Intent`            | Value object    | `text: str` (1 ≤ len ≤ 8 KiB), `submitted_at: datetime`.                   |
| `SystemPrompt`      | Value object    | Immutable rendered prompt, hashable for cache keys.                          |
| `LlmInvocation`     | Value object    | `(provider, model, mode, started_at, completed_at, prompt_tokens, completion_tokens, error_code?)`. |
| `DemoScenario`      | Value object    | `(name, keywords, request)`.                                                |
| `FieldViolation`    | Value object    | Shared across contexts — defined here for now, used elsewhere.              |

## 4. Domain services

| Service              | Responsibility                                                                            |
| -------------------- | ----------------------------------------------------------------------------------------- |
| `IntentParser`       | Build the system prompt, invoke the `LlmProvider`, parse the response.                   |
| `RequestValidator`   | Run the syntactic/lexical/semantic stages. Returns `list[FieldViolation]`.                |
| `RequestEnhancer`    | Apply default `output_dir`, default `description`, type coercion for legacy string types. |
| `DemoCatalog`        | Owns the curated `DemoScenario`s; maps an `Intent` to the closest scenario by keywords.  |
| `LlmInvocationLogger`| Emits `LlmInvocationStarted` / `Succeeded` / `Failed` events.                            |

## 5. Application service

`IntentInterpretationService` exposes:

```python
def parse(self, intent: Intent) -> CodegenRequest:
    """
    1. Build the system prompt.
    2. Try live LLM (with retry/backoff).
    3. On unrecoverable failure & allow_demo_mode → fall back to DemoCatalog.
    4. Validate; raise CodegenRequestRejected if violations exist.
    5. Enhance and return.
    """

def validate(self, request: CodegenRequest) -> list[FieldViolation]: ...
def enhance(self, request: CodegenRequest)  -> CodegenRequest: ...
```

Configuration of allowed providers, retry counts, and demo-mode policy is
injected by the orchestrator at construction time
([`../06-application-services.md §7`](../06-application-services.md#7-composition-root)).

## 6. The system prompt

The system prompt is owned by this context and treated as **versioned
data**. It lives in `prompts/v<N>/intent_interpretation.md` and is
rendered with Jinja2.

Required behaviours encoded in the prompt:

1. Output **only** a JSON object — no preamble, no code fences.
2. Required keys: `group`, `version`, `kind`, `spec_properties`,
   `output_dir`, `description`.
3. `spec_properties` keys are camelCase identifiers; values are objects
   with at least a `type` field.
4. `kind` is CamelCase; `group` is reverse-DNS; `version` is
   `v\d+(alpha|beta)?\d*`.
5. Inferring sensible types ("count of replicas" → `integer`).
6. Conservative on inference: do not invent fields the user did not
   request.

When the LLM provider supports JSON mode, the prompt's structural
requirements are reinforced by `response_format`. When it does not, the
adapter falls back to extracting the last JSON object in the response
and re-prompting on parse failure.

## 7. Demo mode

Demo Mode is **not** a special branch in this context — it is just an
`LlmProvider` adapter (`DemoModeLlmAdapter`).

`DemoCatalog` keys (illustrative):

- `postgres-cluster` — keywords: `postgres`, `postgresql`, `database`
- `redis-cluster` — keywords: `redis`, `cache`
- `vector-db` — keywords: `vector`, `vectordb`, `embedding`
- `notebook` — keywords: `notebook`, `jupyter`, `data science`
- `monitoring-service` — keywords: `monitoring`, `prometheus`, `metrics`

The catalogue lives in
`src/ai_platform_generator/domain/intent/demo_catalog.py` and is covered
by golden-file tests.

When Demo Mode produces a `CodegenRequest`:

- `provider_mode` is set to `ProviderMode.DEMO`.
- A `DemoModeEngaged` event is emitted with the reason code
  (`E_INTENT_LLM_UNAVAILABLE`, `E_INTENT_LLM_AUTH_FAILED`, ...).
- The user-facing renderer prints a visible banner.

## 8. Validation pipeline (this context)

Implemented by `RequestValidator`:

| Stage      | Checks                                                                                          |
| ---------- | ----------------------------------------------------------------------------------------------- |
| Syntactic  | JSON-shaped; required top-level keys present.                                                   |
| Lexical    | `group` regex, `version` regex, `kind` regex.                                                   |
| Semantic   | `spec_properties` non-empty; property names unique; types in the supported set; no `..` in `output_dir`. |

The full taxonomy of errors raised here is in
[ADR-0016](../../adr/0016-validation-pipeline-error-model.md).

## 9. Domain events emitted

| Event                          | When                                                       |
| ------------------------------ | ---------------------------------------------------------- |
| `IntentSubmitted`              | At entry to `parse()`.                                     |
| `LlmInvocationStarted`         | Before the provider's `complete_json` call.                |
| `LlmInvocationSucceeded`       | On a parseable, validated response.                        |
| `LlmInvocationFailed`          | On any provider error.                                     |
| `DemoModeEngaged`              | When `DemoModeLlmAdapter` produces the response.           |
| `CodegenRequestParsed`         | When the aggregate is constructed and validated.           |
| `CodegenRequestRejected`       | When validation produces violations.                       |

## 10. Failure modes and recovery

| Failure                                          | Recovery                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------ |
| `LlmAuthenticationFailed`                        | Demo mode if allowed, else terminal.                                     |
| `LlmUnavailable` (network, SSL, DNS)             | Demo mode if allowed, else terminal.                                     |
| `LlmRateLimited`                                 | Exponential backoff (2, 4, 8 s); if still failing, demo mode.            |
| `LlmResponseUnparseable`                         | Re-prompt once with stricter instructions; if still failing, demo mode.  |
| `CodegenRequestRejected`                         | Terminal — user must rephrase intent.                                    |

## 11. Public contract

Inputs:

- `Intent.text: str` — 1 to 8192 chars, UTF-8.
- Configuration: provider, model, mode policy.

Output:

- `CodegenRequest` — see tactical design for invariants.

Errors raised:

- `IntentInterpretationError` and subclasses
  ([ADR-0016](../../adr/0016-validation-pipeline-error-model.md)).

## 12. Testing strategy

- **Unit:** all domain services with `FakeLlmAdapter` returning canned JSON.
  Coverage target: 95 % of `domain/intent/`.
- **Integration:** at least one test per concrete adapter
  (`OpenRouterLlmAdapter`, `OpenAiLlmAdapter`, `DemoModeLlmAdapter`).
- **Golden:** the demo catalogue produces stable `CodegenRequest`s for each
  scenario keyword set.
- **Property:** random valid LLM outputs always parse without raising
  (`hypothesis`).
- **Adversarial:** malicious / malformed LLM outputs fail with the right
  typed error and never `exec` / `eval`.

## 13. Open questions / future work

- Streaming JSON parsing as completions stream in.
- Few-shot prompt assembly from past successful generations (with explicit
  user opt-in for prompt capture, per [ADR-0020](../../adr/0020-security-threat-model-and-hardening.md)).
- Multi-turn refinement: "make `replicas` an integer 1-7".
