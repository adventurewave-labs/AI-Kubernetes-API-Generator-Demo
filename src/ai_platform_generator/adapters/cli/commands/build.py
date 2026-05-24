"""``build`` Click command — bypass the LLM and build artefacts directly.

Maps to the ``BuildFromRequestFile`` use case
(``docs/ddd/bounded-contexts/05-user-interaction.md`` §4).

Loads a JSON file shaped like :meth:`CodegenRequest.to_dict`, hydrates
the aggregate via :meth:`CodegenRequest.from_dict`, and runs only the
*model* + *generate* (and optionally *provision*) stages of the
orchestrator. The intent-interpretation stage is skipped because the
request is provided verbatim.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from ..exit_codes import EXIT_GENERIC, EXIT_INTERRUPTED, code_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


@click.command("build")
@click.argument(
    "request_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Override the output directory recorded in the request.",
)
@click.pass_context
def build(
    ctx: click.Context,
    request_file: Path,
    output_dir: Path | None,
) -> None:
    """Build artefacts from a JSON CodegenRequest file (skip the LLM step)."""
    opts: dict[str, Any] = ctx.obj["opts"]
    renderer = ctx.obj["renderer"]

    if hasattr(renderer, "begin"):
        with contextlib.suppress(Exception):
            renderer.begin()

    try:
        request = _load_codegen_request(request_file)
    except Exception as exc:
        if hasattr(renderer, "error"):
            with contextlib.suppress(Exception):
                renderer.error(exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    # Apply --output-dir override if given. An absolute path is anchored
    # as the root itself (relative="."); a relative path is resolved
    # against the current working directory.
    cli_output = output_dir or opts.get("output_dir")
    if cli_output is not None:
        from ai_platform_generator.domain.values import OutputPath

        out_path = Path(str(cli_output))
        if out_path.is_absolute():
            request = request.with_output_path(
                OutputPath(root=out_path.resolve(), relative=Path(".")),
            )
        else:
            request = request.with_output_path(
                OutputPath(root=Path.cwd().resolve(), relative=out_path),
            )

    config = _build_app_config(opts, output_override=cli_output)
    try:
        from ai_platform_generator.application.composition import build_orchestrator
    except Exception as exc:  # pragma: no cover - defensive
        if hasattr(renderer, "error"):
            renderer.error(exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)
    orchestrator = build_orchestrator(config)

    try:
        summary = _run_model_and_generate(
            orchestrator,
            request=request,
            deploy=bool(opts.get("deploy", True)),
        )
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERRUPTED)
    except Exception as exc:
        if hasattr(renderer, "error"):
            with contextlib.suppress(Exception):
                renderer.error(exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    if hasattr(renderer, "end"):
        with contextlib.suppress(Exception):
            renderer.end(summary)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_codegen_request(path: Path) -> Any:
    """Read ``path`` and reconstruct a :class:`CodegenRequest`.

    Malformed inputs are normalised to :class:`DomainValidationError`
    so the CLI surfaces exit code 11 rather than the catch-all 1.
    """
    from ai_platform_generator.domain.aggregates.codegen_request import (
        CodegenRequest,
    )
    from ai_platform_generator.domain.errors import DomainValidationError

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DomainValidationError(
            f"request file is not valid JSON: {exc.msg}"
        ) from exc

    try:
        return CodegenRequest.from_dict(data)
    except DomainValidationError:
        raise
    except (KeyError, ValueError, TypeError) as exc:
        raise DomainValidationError(
            f"request file does not satisfy the CodegenRequest schema: {exc}"
        ) from exc


def _build_app_config(
    opts: dict[str, Any], output_override: Any = None
) -> Any:
    """Mirror :func:`generate._build_app_config` without import cycles."""
    from ai_platform_generator.application.composition import AppConfig

    kwargs: dict[str, Any] = {
        "llm_provider": opts.get("llm_provider", "openrouter"),
        "allow_demo_mode": opts.get("allow_demo_mode", True),
        "cluster_name": opts.get("cluster_name", "ai-platform-demo"),
        "log_format": _resolve_log_format(opts),
        "enable_otel": bool(opts.get("otel", False)),
    }
    out_dir = output_override if output_override is not None else opts.get("output_dir")
    if out_dir is not None:
        out_path = Path(str(out_dir)).resolve()
        kwargs["output_dir"] = out_path
        # Anchor the filesystem repo's traversal-safety root at the
        # user-supplied output directory so writes under it are allowed.
        kwargs["artifact_root"] = out_path
    return AppConfig(**kwargs)


def _resolve_log_format(opts: dict[str, Any]) -> str:
    explicit = opts.get("log_format")
    if explicit:
        return str(explicit)
    if not sys.stdout.isatty():
        return "json"
    return "tty"


def _run_model_and_generate(
    orchestrator: Any,
    *,
    request: Any,
    deploy: bool,
) -> Any:
    """Run the post-interpret slice of the saga directly.

    The saga's public entry point is ``run(GenerateParams)``, which
    drives all six stages from the intent text. Here we already have a
    :class:`CodegenRequest`, so we invoke the relevant application
    services in sequence, mirroring the orchestrator's ``_stage`` book-
    keeping but without re-emitting the saga events. Errors raise
    typed :class:`PlatformGeneratorError`s and propagate up.
    """
    from pathlib import Path as _Path

    from ai_platform_generator.application.orchestrator.summary import (
        GenerationSummary,
    )
    from ai_platform_generator.domain.values import RunId

    run_id = RunId.new()
    started_mono = orchestrator._clock.monotonic()

    ir = orchestrator._model.build(request, run_id=run_id)
    target_dir = (
        request.output_path.full
        if hasattr(request.output_path, "full")
        else _Path("generated")
    )
    bundle = orchestrator._generate.run(
        ir, request=request, target_dir=target_dir, run_id=run_id
    )

    cluster_name = None
    deployment_status = None
    if deploy:
        orchestrator._provision.check_prerequisites(run_id=run_id)
        cluster = orchestrator._provision.ensure(
            "ai-platform-demo", run_id=run_id
        )
        deployment = orchestrator._provision.deploy(bundle, cluster, run_id=run_id)
        orchestrator._provision.verify(deployment, cluster, run_id=run_id)
        cluster_name = cluster.name
        deployment_status = "ok"

    duration_ms = int((orchestrator._clock.monotonic() - started_mono) * 1000)
    files = getattr(bundle, "files", ())
    artefact_paths = [
        _Path(getattr(f, "path", ""))
        for f in files
        if getattr(f, "path", None) is not None
    ]
    bundle_dir = getattr(bundle, "target_dir", None)
    return GenerationSummary(
        run_id=run_id,
        state="succeeded",
        gvk=getattr(request, "gvk", None),
        bundle_dir=_Path(bundle_dir) if bundle_dir else None,
        artefact_paths=artefact_paths,
        cluster_name=cluster_name,
        deployment_status=deployment_status,
        duration_ms=duration_ms,
        provider_mode=getattr(request, "provider_mode", None),
    )


__all__ = ["build"]
