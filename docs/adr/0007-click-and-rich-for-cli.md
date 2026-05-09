# ADR-0007: Use Click + Rich for the command-line interface

## Status

Accepted — 2025-05-09

## Context

The User Interaction bounded context
(`docs/ddd/bounded-contexts/05-user-interaction.md`) is the primary surface
through which humans drive the system today. It must support:

- Both **interactive** (REPL-like prompts, multi-step flows) and
  **non-interactive** (single-shot commands, scriptable in CI) modes.
- Helpful command discovery (`--help`, `examples`, `interactive`, `generate`,
  `build`).
- Pretty rendering of progress, panels, trees, and error frames.
- Future extension toward a TUI or web frontend without rewriting business
  logic.

## Decision

We use:

- **[Click](https://click.palletsprojects.com/)** for command parsing,
  argument handling, environment-variable binding, sub-commands, and
  help-text generation.
- **[Rich](https://rich.readthedocs.io/)** for rendering panels, trees,
  progress spinners, and styled error messages.

Both libraries live exclusively in the *User Interaction* adapter layer.
Application services and domain code know nothing about either library —
they raise typed errors and emit progress events that the CLI adapter
renders. This guarantees that swapping the CLI for a TUI, web UI, or REST
API in the future is purely additive.

## Alternatives Considered

| Alternative | Why considered | Why rejected |
| --- | --- | --- |
| `argparse` only | Standard library, no dependency | Verbose; weak ergonomics for nested commands |
| `typer` | Type-hint-driven, modern | Internally built on Click; adds a thin layer with little advantage |
| `prompt_toolkit` | Powerful TUI primitives | Overkill for current needs; better suited to a future TUI ADR |
| Bare `print` + ANSI | No dependency | Reinvents Rich poorly |

## Consequences

### Positive
- Mature, well-documented libraries used by thousands of CLI tools.
- Sub-commands group naturally (`generate`, `interactive`, `build`,
  `examples`, `cluster`, `validate`).
- Rich's rendering primitives match the existing demo aesthetic.

### Negative / Trade-offs
- Two runtime dependencies in the user-interaction adapter.
- Rich output must degrade to plain text in non-TTY contexts (CI logs); the
  adapter must detect this and switch styles accordingly.

### Neutral
- A future Web/TUI frontend remains an open path because all rendering
  decisions live in the adapter.

## Related Decisions

- ADR-0010: Multi-agent layered architecture with explicit bounded contexts
- ADR-0014: Hexagonal (ports and adapters) layering
- ADR-0017: Observability and telemetry strategy
- DDD: `docs/ddd/bounded-contexts/05-user-interaction.md`
