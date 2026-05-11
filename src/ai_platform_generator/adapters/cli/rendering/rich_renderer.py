"""Rich-based renderer for interactive (TTY) sessions.

Implements the :class:`Renderer` Protocol using ``rich.console.Console`` and
``rich.progress.Progress`` to render a stage-aware "live" display. See
``docs/ddd/bounded-contexts/05-user-interaction.md`` §5.1 for the contract.

The renderer purposely keeps **all** Rich/ANSI dependencies inside this module
so the rest of the CLI adapter can stay ANSI-agnostic. Honour ``NO_COLOR`` and
``CLICOLOR=0`` automatically (Rich does this when constructed with
``no_color=True``).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import GenerationSummary
    from ai_platform_generator.domain.errors import PlatformGeneratorError
    from ai_platform_generator.domain.events import DomainEvent


# Stage labels — kept in sync with the orchestrator saga (Wave 2). The order is
# the *display* order; the saga does not need to emit every stage.
_STAGE_ORDER: tuple[str, ...] = (
    "Interpret",
    "Model",
    "Generate",
    "Persist",
    "Provision",
    "Verify",
)

# Map from event payload "stage" identifiers (snake_case, often used by the
# saga) to the human-readable label shown in the progress bar.
_STAGE_ALIASES: dict[str, str] = {
    "interpret": "Interpret",
    "intent": "Interpret",
    "model": "Model",
    "modelling": "Model",
    "ir": "Model",
    "generate": "Generate",
    "generation": "Generate",
    "persist": "Persist",
    "persistence": "Persist",
    "provision": "Provision",
    "cluster": "Provision",
    "verify": "Verify",
    "verification": "Verify",
}


def _no_color_from_env() -> bool:
    """Return ``True`` if ``NO_COLOR`` or ``CLICOLOR=0`` is set."""
    if os.environ.get("NO_COLOR"):
        return True
    return os.environ.get("CLICOLOR") == "0"


def _resolve_stage_label(stage: Any) -> str | None:
    """Return the canonical stage label for a payload value, or ``None``."""
    if not isinstance(stage, str):
        return None
    if stage in _STAGE_ORDER:
        return stage
    return _STAGE_ALIASES.get(stage.lower())


class RichRenderer:
    """A renderer that paints a Rich live display for human consumption."""

    def __init__(
        self,
        console: Console | None = None,
        theme: Theme | None = None,
    ) -> None:
        if console is None:
            console = Console(
                stderr=False,
                force_terminal=False,
                no_color=_no_color_from_env(),
                theme=theme,
            )
        self.console = console
        self._progress: Progress | None = None
        self._task_ids: dict[str, TaskID] = {}
        self._active_stage: str | None = None
        self._debug: bool = bool(os.environ.get("AIPG_DEBUG"))

    # ------------------------------------------------------------------ begin
    def begin(self) -> None:
        """Print the welcome banner."""
        banner = (
            "🚀 AI Kubernetes API Generator\n"
            "Natural language → production CRDs"
        )
        self.console.print(
            Panel.fit(banner, border_style="cyan", padding=(0, 2))
        )

    # ------------------------------------------------------------------ event
    def event(self, event: DomainEvent) -> None:
        """Render a single domain event."""
        name = event.name
        payload = dict(event.payload or {})

        if name == "RunStarted":
            self._on_run_started()
            return
        if name == "StageStarted":
            self._on_stage_started(payload)
            return
        if name == "StageSucceeded":
            self._on_stage_succeeded(payload)
            return
        if name == "StageFailed":
            self._on_stage_failed(payload)
            return
        if name == "LlmInvocationSucceeded":
            self._on_llm_succeeded(payload)
            return
        if name == "DemoModeEngaged":
            self._on_demo_mode(payload)
            return
        if name == "ArtifactGenerated":
            self._on_artifact_generated(payload)
            return
        if name == "ArtifactBundleSealed":
            self._on_bundle_sealed(payload)
            return
        # Anything else: only show in debug mode.
        if self._debug:
            self.console.print(f"[dim][debug] {name} {payload}[/dim]")

    # -------------------------------------------------------------------- end
    def end(self, summary: GenerationSummary) -> None:
        """Render the run summary panel and stop the live display."""
        self._stop_progress()

        gvk = getattr(summary, "gvk", None)
        bundle_dir = getattr(summary, "bundle_dir", None)
        artefact_count = len(getattr(summary, "artefact_paths", []) or [])
        cluster_name = getattr(summary, "cluster_name", None)
        deployment_status = getattr(summary, "deployment_status", None)
        duration_ms = getattr(summary, "duration_ms", 0) or 0
        provider_mode = getattr(summary, "provider_mode", None)

        provider_str = (
            getattr(provider_mode, "value", None)
            or getattr(provider_mode, "name", None)
            or (str(provider_mode) if provider_mode is not None else "live")
        )

        lines = [
            f"GVK: {gvk if gvk is not None else '(none)'}",
            f"Output dir: {bundle_dir if bundle_dir is not None else '(none)'}",
            f"Artefacts: {artefact_count}",
            (
                "Deployment: "
                f"{deployment_status if deployment_status is not None else '(skipped)'}"
                + (f" on {cluster_name}" if cluster_name else "")
            ),
            f"Duration: {duration_ms} ms",
            f"Mode: {provider_str}",
        ]
        body = "\n".join(lines)
        self.console.print(
            Panel(body, title="✅ Run summary", border_style="green")
        )

    # ------------------------------------------------------------------ error
    def error(self, error: PlatformGeneratorError) -> int:
        """Render the error panel and return the appropriate exit code."""
        self._stop_progress()

        from ai_platform_generator.adapters.cli.exit_codes import code_for

        code = getattr(error, "code", "E_PLATFORM_GENERIC")
        user_message = getattr(error, "user_message", str(error))
        remediation = getattr(error, "remediation_hint", None)
        if not remediation:
            extra = getattr(error, "extra", {}) or {}
            remediation = extra.get("remediation_hint") or extra.get(
                "remediation"
            )
        if not remediation:
            remediation = "(none)"

        body = Text()
        body.append(f"❌ {code}\n", style="bold red")
        body.append(f"{user_message}\n\n")
        body.append(f"Remediation: {remediation}", style="yellow")
        self.console.print(Panel(body, title="Error", border_style="red"))

        return code_for(error)

    # ------------------------------------------------------------------ helpers
    def _on_run_started(self) -> None:
        if self._progress is not None:
            return
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        progress.start()
        self._progress = progress
        self._task_ids = {}
        for label in _STAGE_ORDER:
            task_id = progress.add_task(label, total=1, start=False)
            self._task_ids[label] = task_id

    def _on_stage_started(self, payload: dict[str, Any]) -> None:
        label = _resolve_stage_label(payload.get("stage"))
        if label is None or self._progress is None:
            return
        task_id = self._task_ids.get(label)
        if task_id is None:
            return
        self._active_stage = label
        self._progress.start_task(task_id)
        self._progress.update(task_id, description=f"{label} (running)")

    def _on_stage_succeeded(self, payload: dict[str, Any]) -> None:
        label = _resolve_stage_label(payload.get("stage"))
        if label is None or self._progress is None:
            return
        task_id = self._task_ids.get(label)
        if task_id is None:
            return
        elapsed = payload.get("elapsed_ms")
        suffix = f" — {elapsed} ms" if elapsed is not None else ""
        self._progress.update(
            task_id,
            description=f"[green]✓ {label}{suffix}[/green]",
            completed=1,
        )
        if self._active_stage == label:
            self._active_stage = None

    def _on_stage_failed(self, payload: dict[str, Any]) -> None:
        label = _resolve_stage_label(payload.get("stage"))
        if label is None or self._progress is None:
            return
        task_id = self._task_ids.get(label)
        if task_id is None:
            return
        self._progress.update(
            task_id,
            description=f"[red]✗ {label} (failed)[/red]",
            completed=1,
        )
        if self._active_stage == label:
            self._active_stage = None

    def _on_llm_succeeded(self, payload: dict[str, Any]) -> None:
        prompt = payload.get("prompt_tokens", 0)
        completion = payload.get("completion_tokens", 0)
        self.console.print(
            f"   [dim]tokens: {prompt}+{completion}[/dim]"
        )

    def _on_demo_mode(self, payload: dict[str, Any]) -> None:
        reason = payload.get("reason") or payload.get("code") or "unspecified"
        message = (
            f"⚠ Running in demo mode (reason: {reason}). "
            "The generated artefacts use a curated demo scenario, not your intent."
        )
        self.console.print(
            Panel(message, border_style="yellow", title="Demo mode")
        )

    def _on_artifact_generated(self, payload: dict[str, Any]) -> None:
        kind = (
            payload.get("artifact_type")
            or payload.get("type")
            or payload.get("kind")
            or "artifact"
        )
        path = payload.get("path") or payload.get("target") or "(unknown)"
        self.console.print(f"   [green]✓[/green] generated {kind}: {path}")

    def _on_bundle_sealed(self, payload: dict[str, Any]) -> None:
        target = (
            payload.get("target_dir")
            or payload.get("bundle_dir")
            or payload.get("path")
            or "(unknown)"
        )
        self.console.print(f"   [green]✓[/green] bundle sealed at {target}")

    def _stop_progress(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task_ids = {}
            self._active_stage = None


__all__ = ["RichRenderer"]
