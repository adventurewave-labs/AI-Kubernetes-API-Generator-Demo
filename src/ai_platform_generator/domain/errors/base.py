"""Base exception type for the platform generator.

All typed errors in the platform inherit from :class:`PlatformGeneratorError`.
The base class establishes the contract used by the CLI renderer and the
orchestrator's recovery logic (see ADR-0016):

* ``code``       — stable string identifier (e.g. ``E_INTENT_LLM_UNAVAILABLE``)
                   carried at the *class* level so it is part of the type's
                   public contract.
* ``user_message`` — human-friendly, actionable string (instance attribute).
* ``recoverable`` — class-level flag indicating whether the orchestrator
                    may retry, back off, or fall back to demo mode.
* ``cause``      — the originating exception, also chained via ``__cause__``
                   so that ``raise X from cause`` semantics still work.
* ``extra``      — arbitrary keyword data captured at construction time;
                   used by telemetry and error-rendering layers.
"""
from __future__ import annotations

from typing import Any


class PlatformGeneratorError(Exception):
    """Root of the platform generator's typed exception hierarchy."""

    #: Stable error code. Subclasses MUST override.
    code: str = "E_PLATFORM_GENERIC"

    #: Whether the orchestrator may retry / degrade on this error.
    recoverable: bool = False

    def __init__(
        self,
        user_message: str,
        *,
        cause: Exception | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(user_message)
        self.user_message: str = user_message
        self.cause: Exception | None = cause
        self.extra: dict[str, Any] = dict(extra)
        if cause is not None:
            # Preserve standard exception-chaining semantics so that
            # ``raise X(...) from original`` and constructor-time chaining
            # both produce the same traceback shape.
            self.__cause__ = cause

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.user_message}"

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"{type(self).__name__}(code={self.code!r}, "
            f"user_message={self.user_message!r}, "
            f"recoverable={self.recoverable!r}, extra={self.extra!r})"
        )
