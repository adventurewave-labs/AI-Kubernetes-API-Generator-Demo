"""Stable CLI exit-code mapping.

Realises the table in
``docs/ddd/bounded-contexts/05-user-interaction.md`` §7. The codes are
part of the tool's *public contract* per ADR-0019: renaming or
re-shuffling them is a major-version bump.

The :func:`code_for` helper performs the *single* ``isinstance`` walk
that maps a typed :class:`PlatformGeneratorError` (Wave-1 taxonomy) to
its exit code. Subclass relationships in the taxonomy mean the order
of checks below is deliberate — the most-specific group must be
listed before its parent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.errors import PlatformGeneratorError


# ---------------------------------------------------------------------------
# Public constants — in the table order from §7
# ---------------------------------------------------------------------------

EXIT_OK: int = 0
EXIT_GENERIC: int = 1
EXIT_INVALID_USAGE: int = 2
EXIT_INTENT: int = 10
EXIT_DOMAIN_VALIDATION: int = 11
EXIT_ARTIFACT: int = 12
EXIT_PERSISTENCE: int = 13
EXIT_CLUSTER: int = 14
EXIT_CONFIGURATION: int = 15
EXIT_INTERRUPTED: int = 130


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def code_for(exc: PlatformGeneratorError | BaseException | None) -> int:
    """Map a typed error to its stable exit code.

    Parameters
    ----------
    exc:
        ``None`` → :data:`EXIT_OK`. A :class:`KeyboardInterrupt` →
        :data:`EXIT_INTERRUPTED`. A typed
        :class:`PlatformGeneratorError` is walked against the taxonomy
        and resolved to its category. Anything else (untyped
        ``Exception``) → :data:`EXIT_GENERIC`.
    """
    if exc is None:
        return EXIT_OK
    if isinstance(exc, KeyboardInterrupt):
        return EXIT_INTERRUPTED

    # Lazy import keeps this module light and avoids a circular import
    # if a renderer pulls in ``exit_codes`` before the error taxonomy
    # has loaded.
    from ai_platform_generator.domain.errors import (
        ArtifactGenerationError,
        ClusterProvisioningError,
        ConfigurationError,
        DomainValidationError,
        IntentInterpretationError,
        PersistenceError,
        PlatformGeneratorError,
    )

    if not isinstance(exc, PlatformGeneratorError):
        return EXIT_GENERIC

    # Order: subclass-specific groups first; ``PlatformGeneratorError``
    # itself is the catch-all.
    if isinstance(exc, IntentInterpretationError):
        return EXIT_INTENT
    if isinstance(exc, DomainValidationError):
        return EXIT_DOMAIN_VALIDATION
    if isinstance(exc, ArtifactGenerationError):
        return EXIT_ARTIFACT
    if isinstance(exc, PersistenceError):
        return EXIT_PERSISTENCE
    if isinstance(exc, ClusterProvisioningError):
        return EXIT_CLUSTER
    if isinstance(exc, ConfigurationError):
        return EXIT_CONFIGURATION
    return EXIT_GENERIC


__all__ = [
    "EXIT_ARTIFACT",
    "EXIT_CLUSTER",
    "EXIT_CONFIGURATION",
    "EXIT_DOMAIN_VALIDATION",
    "EXIT_GENERIC",
    "EXIT_INTENT",
    "EXIT_INTERRUPTED",
    "EXIT_INVALID_USAGE",
    "EXIT_OK",
    "EXIT_PERSISTENCE",
    "code_for",
]
