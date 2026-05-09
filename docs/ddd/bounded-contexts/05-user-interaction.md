# Bounded Context — User Interaction

> **Purpose:** present the system to humans (and to scripts) through a CLI
> today and additional surfaces (TUI, web) tomorrow, without leaking
> presentation concerns into the domain.

This is a **supporting** subdomain. It is the **only** place where Click,
Rich, ANSI codes, or terminal capabilities are imported.

---

## 1. Responsibilities

1. Parse command-line invocations and bind them to application services.
2. Render `DomainEvent`s as terminal output (TTY) or structured logs (CI).
3. Run interactive prompts and progressive disclosure flows.
4. Produce stable exit codes mapped to the error taxonomy
   ([ADR-0016](../../adr/0016-validation-pipeline-error-model.md)).
5. Treat the user as a first-class citizen: clear, actionable errors;
   honest progress; no silent fallback (Demo Mode banner).

This context **does not**:

- Construct domain aggregates directly.
- Make any decisions about retry, fallback, or compensation (those are
  application-service / orchestrator decisions).
- Talk to the LLM, filesystem, or cluster directly.

## 2. Ubiquitous language

Originated here: **Command**, **Interactive Session**, **Renderer**,
**Render Mode**.

## 3. Architecture inside the context

```
adapters/cli/
├── main.py                      ← Click `main` group, version, common options
├── commands/
│   ├── generate.py              ← `generate` (one-shot)
│   ├── interactive.py           ← `interactive` (REPL-like)
│   ├── build.py                 ← `build` (from a request file)
│   ├── examples.py              ← `examples`
│   ├── cluster.py               ← `cluster ensure|teardown|status`
│   └── validate.py              ← `validate <request file>`
├── rendering/
│   ├── renderer.py              ← Renderer Protocol
│   ├── rich_renderer.py         ← Rich-based TTY output
│   ├── json_renderer.py         ← line-delimited JSON
│   └── quiet_renderer.py        ← no-op
└── exit_codes.py                ← stable exit-code mapping
```

## 4. Commands

| Command                    | Maps to use case                                                    |
| -------------------------- | ------------------------------------------------------------------- |
| `generate <description>`   | `GenerateFromIntent`                                                |
| `interactive`              | `GenerateFromIntent` (loop)                                         |
| `build <request-file>`     | `BuildFromRequestFile`                                              |
| `examples`                 | `ListExamples`                                                      |
| `cluster ensure <name>`    | `EnsureCluster`                                                     |
| `cluster teardown <name>`  | `TeardownCluster`                                                   |
| `cluster status <name>`    | reads `ClusterRepository`                                           |
| `validate <request-file>`  | `ValidateRequest`                                                   |
| `runs list / show <id>`    | reads `RunRepository`                                               |
| `version`                  | prints `tool_version` + git SHA                                     |

Common options (bound at the `main` group level):

- `--output-dir PATH` (default `./generated_specs/<kind>`).
- `--no-deploy / --deploy` (default `--deploy`).
- `--no-fallback` (disable Demo Mode; CI-friendly).
- `--api-key TEXT` (overrides `OPENROUTER_API_KEY`).
- `--model TEXT` (overrides `OPENROUTER_MODEL`).
- `--log-format [tty|json|quiet]` (auto-detected if not given).
- `--debug` (enables verbose logging).
- `--otel` (enables OpenTelemetry sink).

## 5. Rendering

The `Renderer` Protocol:

```python
class Renderer(Protocol):
    def begin(self) -> None: ...
    def event(self, event: DomainEvent) -> None: ...
    def end(self, summary: GenerationSummary) -> None: ...
    def error(self, error: PlatformGeneratorError) -> int: ...
```

### 5.1 `RichRenderer` (TTY default)

- Uses Rich's `Live` display for stage progress.
- Per stage: a panel with title, spinner, started/elapsed time.
- On `LlmInvocationSucceeded`: token counts in dim text.
- On `DemoModeEngaged`: a yellow banner — *"Running in demo mode (reason:
  {code}). The generated artefacts use a curated demo scenario, not your
  intent."*
- On `ArtifactGenerated`: a tree view of the bundle directory.
- On error: a panel with title `Error <code>`, the message, and the
  remediation hint (if available).

### 5.2 `JsonRenderer` (CI default when stdout is not a TTY)

- One JSON object per line.
- Each object is a serialised `DomainEvent`.
- The final line is a `RunSucceeded` or `RunFailed` event.
- Suitable for `jq` and log-aggregation pipelines.

### 5.3 `QuietRenderer`

- Emits nothing on stdout.
- Errors go to stderr with the bare error code.

## 6. Interactive session

The `interactive` command loops:

1. Print a welcome panel listing recent runs (if any).
2. Prompt for an intent (with multiline support).
3. Run the orchestrator.
4. Render the summary.
5. Offer next-step actions: `[d]eploy`, `[r]egenerate`, `[e]dit`, `[q]uit`.

Configuration captured at session start (model, output dir, deploy flag)
applies to subsequent runs unless overridden inline.

## 7. Exit codes

Stable mapping (per [ADR-0019](../../adr/0019-versioning-release-and-packaging.md)):

| Exit code | Meaning                                                   |
| --------- | --------------------------------------------------------- |
| `0`       | Success.                                                  |
| `1`       | Generic / uncaught error.                                  |
| `2`       | Invalid CLI invocation (Click-detected).                   |
| `10`      | `IntentInterpretationError`.                               |
| `11`      | `DomainValidationError`.                                   |
| `12`      | `ArtifactGenerationError`.                                 |
| `13`      | `PersistenceError`.                                        |
| `14`      | `ClusterProvisioningError`.                                 |
| `15`      | `ConfigurationError`.                                      |
| `130`     | Interrupted (`KeyboardInterrupt`).                         |

## 8. Domain events emitted

| Event                  | When                                                           |
| ---------------------- | -------------------------------------------------------------- |
| `CommandStarted`       | At entry to a command.                                          |
| `CommandSucceeded`     | On exit code 0.                                                 |
| `CommandFailed`        | On non-zero exit.                                               |
| `RenderModeChosen`     | Once, at startup, before any output.                            |

## 9. Accessibility and locale

- Rich rendering must degrade in non-TTY mode without losing information.
- Avoid emoji-only signals; always pair an emoji with a textual cue
  (e.g. `✅ ok`, `❌ failed`).
- Colour conventions:
  - Green: success.
  - Yellow: warning, demo-mode banner.
  - Red: error.
  - Blue: informational paths and identifiers.
- Honour `NO_COLOR` and `CLICOLOR=0` environment variables.

## 10. Public contract

The CLI is part of the tool's public API
([ADR-0019](../../adr/0019-versioning-release-and-packaging.md)). Renaming
a command or removing an option is a major-version change.

## 11. Testing strategy

- **Unit:** Click commands tested via `CliRunner` with stub application
  services.
- **Integration:** real composition root with stub adapters; assert
  rendered output against snapshots (`tests/golden/cli/`).
- **End-to-end:** `./run.sh demo` runs a real CLI invocation and asserts
  exit code 0 and the presence of expected artefacts.

## 12. Future surfaces

- **TUI:** `prompt_toolkit`-based, sharing the Renderer Protocol.
- **Web UI:** read-only at first; show `RunRepository` history.
- **REST API:** wraps the same application services; a separate adapter.
- **GitHub Action:** a thin wrapper around the CLI in `--log-format=json`
  mode.
