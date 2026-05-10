"""A single, structured field-level validation violation.

``FieldViolation`` records *one* problem with an input field. The validation
pipeline (ADR-0016) collects many of these and attaches them to a
:class:`~ai_platform_generator.domain.errors.domain_validation.DomainValidationError`
so the user can fix every problem in a single iteration.

``path`` is a JSON-pointer-ish dotted path into the request, e.g.
``"spec_properties.replicas.type"``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldViolation:
    """One field-level validation problem.

    Attributes:
        path:     Dotted JSON-pointer-ish path identifying the field
                  (e.g. ``"spec_properties.replicas.type"``).
        expected: Short description of what was expected.
        actual:   Short description of what was actually provided.
        message:  Human-friendly, actionable description of the problem.
    """

    path: str
    expected: str
    actual: str
    message: str
