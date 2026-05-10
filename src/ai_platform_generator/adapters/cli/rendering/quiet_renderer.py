"""Silent renderer used when ``--log-format=quiet`` or output is redirected.

All informational methods are no-ops; only :meth:`error` writes a single line
(the bare error code) to stderr. The exit code is still resolved via
:func:`ai_platform_generator.adapters.cli.exit_codes.code_for` so wrapper
scripts get the correct numeric signal even with no chatter on stdout.

See ``docs/ddd/bounded-contexts/05-user-interaction.md`` §5.3.
"""
from __future__ import annotations

import sys
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.application.orchestrator import GenerationSummary
    from ai_platform_generator.domain.errors import PlatformGeneratorError
    from ai_platform_generator.domain.events import DomainEvent


class QuietRenderer:
    """A no-op renderer for ``--log-format=quiet`` mode."""

    def __init__(self, stderr: IO[str] | None = None) -> None:
        self.stderr: IO[str] = stderr if stderr is not None else sys.stderr

    def begin(self) -> None:
        """No-op."""
        return None

    def event(self, event: DomainEvent) -> None:
        """No-op."""
        del event
        return None

    def end(self, summary: GenerationSummary) -> None:
        """No-op."""
        del summary
        return None

    def error(self, error: PlatformGeneratorError) -> int:
        """Write the bare error code to stderr; return the exit code."""
        from ai_platform_generator.adapters.cli.exit_codes import code_for

        code = getattr(error, "code", "E_PLATFORM_GENERIC")
        self.stderr.write(f"{code}\n")
        flush = getattr(self.stderr, "flush", None)
        if callable(flush):
            flush()
        return code_for(error)


__all__ = ["QuietRenderer"]
