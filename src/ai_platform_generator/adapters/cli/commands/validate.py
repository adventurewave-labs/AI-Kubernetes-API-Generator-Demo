"""``validate`` Click command — validate a CodegenRequest file.

Maps to the ``ValidateRequest`` use case
(``docs/ddd/bounded-contexts/05-user-interaction.md`` §4).

Loads the JSON payload, hydrates a :class:`CodegenRequest`, and runs
:meth:`IntentInterpretationService.validate`. Renders either the list
of :class:`FieldViolation`s or a green checkmark.
"""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from ..exit_codes import (
    EXIT_DOMAIN_VALIDATION,
    EXIT_GENERIC,
    EXIT_OK,
    code_for,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


@click.command("validate")
@click.argument("request_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def validate(ctx: click.Context, request_file: Path) -> None:
    """Validate a CodegenRequest file without generating."""
    renderer = ctx.obj["renderer"]

    try:
        request = _load_request(request_file)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    service = _build_validation_service(ctx)
    try:
        violations = service.validate(request)
    except Exception as exc:
        _report_error(renderer, exc)
        sys.exit(code_for(exc) or EXIT_GENERIC)

    if violations:
        forwarded = _try_render(renderer, "render_violations", violations)
        if not forwarded:
            for v in violations:
                click.echo(
                    f"  - {getattr(v, 'path', '?')}: "
                    f"{getattr(v, 'message', '')}",
                    err=True,
                )
        sys.exit(EXIT_DOMAIN_VALIDATION)

    forwarded = _try_render(renderer, "render_validation_ok", request)
    if not forwarded:
        click.echo("✓ valid")
    sys.exit(EXIT_OK)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_request(path: Path) -> Any:
    """Read ``path`` and reconstruct a :class:`CodegenRequest`.

    A malformed payload (missing required keys, unparseable JSON,
    invalid value types) is normalised to :class:`DomainValidationError`
    so the CLI surfaces exit code 11 — the contract for "request file
    is structurally invalid" — rather than the catch-all generic
    code 1.
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


def _build_validation_service(ctx: click.Context) -> Any:
    """Build a service instance suitable for ``.validate``.

    Constructing the full :class:`IntentInterpretationService` requires
    an LLM port we don't actually need here — we want a pure validator.
    A no-op LLM stub satisfies the constructor without engaging any
    network path; the validator is consulted as-is.
    """
    from ai_platform_generator.application.services.intent_interpretation import (
        IntentInterpretationService,
    )
    from ai_platform_generator.domain.values import ProviderMode

    opts: dict[str, Any] = ctx.obj.get("opts", {})

    class _NoOpSink:
        def emit(self, _event: Any) -> None:  # pragma: no cover - trivial
            return None

        def flush(self) -> None:  # pragma: no cover - trivial
            return None

    class _StubLlm:
        name = "stub"
        model = "stub"
        mode = ProviderMode.LIVE

        def complete_json(self, *_a: Any, **_kw: Any) -> dict[str, Any]:  # pragma: no cover
            return {}

        def is_available(self) -> bool:  # pragma: no cover
            return True

    class _StubClock:
        def now(self) -> Any:  # pragma: no cover
            from datetime import datetime

            return datetime.now(UTC)

        def monotonic(self) -> float:  # pragma: no cover
            import time

            return time.monotonic()

    return IntentInterpretationService(
        llm=_StubLlm(),
        validator=None,
        enhancer=None,
        events=_NoOpSink(),
        clock=_StubClock(),
        allow_demo_mode=bool(opts.get("allow_demo_mode", True)),
    )


def _try_render(renderer: Any, method: str, payload: Any) -> bool:
    """Call ``renderer.<method>(payload)`` if present; swallow errors."""
    fn = getattr(renderer, method, None)
    if fn is None:
        return False
    try:
        fn(payload)
    except Exception:
        return False
    return True


def _report_error(renderer: Any, exc: Exception) -> None:
    """Forward ``exc`` to the renderer; swallow rendering failures."""
    if hasattr(renderer, "error"):
        with contextlib.suppress(Exception):
            renderer.error(exc)


__all__ = ["validate"]
