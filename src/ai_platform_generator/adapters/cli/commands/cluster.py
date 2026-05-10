"""``cluster`` Click sub-group — manage Kubernetes clusters.

Three sub-commands per
``docs/ddd/bounded-contexts/05-user-interaction.md`` §4:

* ``ensure``   — wraps :meth:`ClusterProvisioningService.ensure`.
* ``teardown`` — wraps :meth:`ClusterProvisioningService.teardown`.
* ``status``   — reads the runtime's ``cluster_status``.

Each sub-command honours the ``--cluster-name`` global option as the
default for its positional ``name`` argument so users can either type
``cluster ensure my-cluster`` or rely on the group-level default.
"""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING, Any

import click

from ..exit_codes import EXIT_GENERIC, code_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


@click.group("cluster")
def cluster() -> None:
    """Manage Kubernetes clusters."""


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


@cluster.command("ensure")
@click.argument("name", default="ai-platform-demo")
@click.pass_context
def cluster_ensure(ctx: click.Context, name: str) -> None:
    """Ensure ``name`` exists and is ready, creating it if necessary."""
    renderer = ctx.obj["renderer"]
    service = _build_service(ctx)

    try:
        result = service.ensure(name)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    click.echo(f"cluster '{getattr(result, 'name', name)}' ready")
    sys.exit(0)


@cluster.command("teardown")
@click.argument("name", default="ai-platform-demo")
@click.pass_context
def cluster_teardown(ctx: click.Context, name: str) -> None:
    """Delete ``name`` (idempotent on absence)."""
    renderer = ctx.obj["renderer"]
    service = _build_service(ctx)

    try:
        service.teardown(name)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    click.echo(f"cluster '{name}' torn down")
    sys.exit(0)


@cluster.command("status")
@click.argument("name", default="ai-platform-demo")
@click.pass_context
def cluster_status(ctx: click.Context, name: str) -> None:
    """Report whether ``name`` exists and is ready."""
    renderer = ctx.obj["renderer"]
    opts: dict[str, Any] = ctx.obj.get("opts", {})
    service = _build_service(ctx)
    runtime = getattr(service, "_runtime", None)
    if runtime is None:
        click.echo("cluster runtime unavailable", err=True)
        sys.exit(EXIT_GENERIC)

    try:
        status = runtime.cluster_status(name)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    payload = {
        "name": name,
        "exists": bool(getattr(status, "exists", False)),
        "ready": bool(getattr(status, "ready", False)),
    }
    if (opts.get("log_format") or "tty") == "json":
        import json as _json

        click.echo(_json.dumps(payload, sort_keys=True))
    else:
        click.echo(
            f"cluster '{name}': "
            f"exists={payload['exists']} ready={payload['ready']}"
        )
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_service(ctx: click.Context) -> Any:
    """Materialise a fully-wired :class:`ClusterProvisioningService`.

    Cluster commands do not need an LLM or a generator — wiring through
    :func:`build_orchestrator` would be overkill (and tests stub the
    orchestrator with a lightweight fake that doesn't expose
    ``_provision``). We construct the service directly here from the
    runtime adapter the user picked.
    """
    from ai_platform_generator.adapters.clock.system import SystemClock
    from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime
    from ai_platform_generator.adapters.telemetry.recording import RecordingSink
    from ai_platform_generator.application.services.cluster_provisioning import (
        ClusterProvisioningService,
    )

    _ = ctx  # global options are not currently consumed here
    runtime = KindClusterRuntime()
    return ClusterProvisioningService(
        runtime=runtime, events=RecordingSink(), clock=SystemClock()
    )


def _report_error(renderer: Any, exc: Exception) -> None:
    """Forward ``exc`` to the renderer; swallow rendering failures."""
    if hasattr(renderer, "error"):
        with contextlib.suppress(Exception):
            renderer.error(exc)


__all__ = ["cluster"]
