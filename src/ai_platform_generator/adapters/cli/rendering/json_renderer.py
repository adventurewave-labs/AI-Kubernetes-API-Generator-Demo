"""NDJSON-based renderer for CI / non-TTY pipelines.

Each :class:`Renderer` method writes exactly *one* JSON object per line to the
configured stream (stdout by default). The wire format is documented in
``docs/ddd/bounded-contexts/05-user-interaction.md`` §5.2 — one envelope per
line, suitable for ``jq`` and log shippers.

Serialisation defers to :func:`_json_default` for non-trivial Python types
(``Path``, ``UUID``, ``datetime``, ``Enum``, ``bytes``, Pydantic models). The
renderer never reaches into the domain model.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import IO, TYPE_CHECKING, Any

from ._json_default import _json_default

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import GenerationSummary
    from ai_platform_generator.domain.errors import PlatformGeneratorError
    from ai_platform_generator.domain.events import DomainEvent


# Bumped only when the line schema changes in a non-additive way. Consumers
# may pin against this value; see ADR-0019 for stability guarantees.
_TOOL_VERSION = "0.1.0"


def _utc_now_iso() -> str:
    return (
        datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )


class JsonRenderer:
    """A renderer that emits one JSON object per call, NDJSON-style."""

    def __init__(self, stream: IO[str] | None = None) -> None:
        self.stream: IO[str] = stream if stream is not None else sys.stdout

    # ------------------------------------------------------------------ begin
    def begin(self) -> None:
        """Emit the ``command_started`` line."""
        self._write_line(
            {
                "type": "command_started",
                "ts": _utc_now_iso(),
                "tool_version": _TOOL_VERSION,
            }
        )

    # ------------------------------------------------------------------ event
    def event(self, event: DomainEvent) -> None:
        """Emit a ``domain_event`` line wrapping the envelope."""
        envelope = event.to_dict()
        line: dict[str, Any] = {"type": "domain_event"}
        line.update(envelope)
        self._write_line(line)

    # -------------------------------------------------------------------- end
    def end(self, summary: GenerationSummary) -> None:
        """Emit the ``summary`` line derived from ``GenerationSummary``."""
        # Pydantic ``model_dump_json`` round-trips through JSON (so nested
        # ``Path``/``UUID`` instances are already strings); we reload it to a
        # dict so we can attach the ``type`` discriminator.
        try:
            payload = json.loads(summary.model_dump_json())
        except AttributeError:
            # Fallback for non-pydantic test doubles.
            payload = json.loads(
                json.dumps(dict(getattr(summary, "__dict__", {})), default=_json_default)
            )
        line: dict[str, Any] = {"type": "summary"}
        line.update(payload)
        self._write_line(line)

    # ------------------------------------------------------------------ error
    def error(self, error: PlatformGeneratorError) -> int:
        """Emit an ``error`` line and return the resolved exit code."""
        from ai_platform_generator.adapters.cli.exit_codes import code_for

        code = getattr(error, "code", "E_PLATFORM_GENERIC")
        user_message = getattr(error, "user_message", str(error))
        extras = dict(getattr(error, "extra", {}) or {})

        self._write_line(
            {
                "type": "error",
                "code": code,
                "user_message": user_message,
                "extras": extras,
            }
        )
        return code_for(error)

    # ------------------------------------------------------------------ helpers
    def _write_line(self, obj: dict[str, Any]) -> None:
        line = json.dumps(obj, default=_json_default, ensure_ascii=False)
        self.stream.write(line + "\n")
        # Flushing is mandatory: log shippers (and tests) may consume the
        # stream incrementally.
        flush = getattr(self.stream, "flush", None)
        if callable(flush):
            flush()


__all__ = ["JsonRenderer"]
