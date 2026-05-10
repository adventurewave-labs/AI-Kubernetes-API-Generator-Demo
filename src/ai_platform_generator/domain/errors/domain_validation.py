"""Domain-validation errors.

These are raised when a parsed request fails domain invariants — invalid
group, invalid version, invalid kind, empty spec, unsupported schema. Each
carries a (possibly empty) list of :class:`FieldViolation` objects so the
CLI can render every problem at once.

NOTE: This module deliberately does *not* import from
``ai_platform_generator.domain.values``: the value objects raise these
exceptions in their ``__post_init__``, and we need to avoid an import cycle.
"""
from __future__ import annotations

from typing import Any

from .base import PlatformGeneratorError
from .field_violation import FieldViolation


class DomainValidationError(PlatformGeneratorError):
    """Base class for domain-invariant violations.

    Attributes:
        field_violations: Zero or more structured per-field violations.
    """

    code = "E_DOMAIN_GENERIC"

    def __init__(
        self,
        user_message: str,
        *,
        field_violations: list[FieldViolation] | None = None,
        cause: Exception | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(user_message, cause=cause, **extra)
        self.field_violations: list[FieldViolation] = list(field_violations or [])


class InvalidGroup(DomainValidationError):
    """The API group does not match the reverse-DNS regex."""

    code = "E_DOMAIN_INVALID_GROUP"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid API group {value!r}: expected reverse-DNS notation "
            "(e.g. 'platform.example.com')."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidVersion(DomainValidationError):
    """The API version does not match the Kubernetes alpha/beta/stable regex."""

    code = "E_DOMAIN_INVALID_VERSION"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid API version {value!r}: expected Kubernetes-compatible "
            "version such as 'v1', 'v1alpha1', or 'v2beta3'."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidKind(DomainValidationError):
    """The kind is not CamelCase / not a valid Go identifier."""

    code = "E_DOMAIN_INVALID_KIND"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid kind {value!r}: expected CamelCase identifier "
            "(e.g. 'PostgresCluster')."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class EmptySpec(DomainValidationError):
    """The CodegenRequest has no spec properties at all."""

    code = "E_DOMAIN_EMPTY_SPEC"

    def __init__(
        self,
        value: Any = None,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            "Spec is empty: at least one spec property is required to "
            "generate a meaningful CRD."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class UnsupportedSchema(DomainValidationError):
    """The schema uses constructs we cannot yet codegen (oneOf, allOf, ...)."""

    code = "E_DOMAIN_UNSUPPORTED_SCHEMA"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Unsupported schema construct {value!r}: this generator does "
            "not yet handle that shape."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidChecksum(DomainValidationError):
    """The checksum value is not a 64-char lowercase hex SHA-256."""

    code = "E_DOMAIN_INVALID_CHECKSUM"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid checksum {value!r}: expected 64-char lowercase hex "
            "SHA-256 digest."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidRunId(DomainValidationError):
    """The run-id is not a valid UUID."""

    code = "E_DOMAIN_INVALID_RUN_ID"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = f"Invalid run id {value!r}: expected a UUID string."
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidIntent(DomainValidationError):
    """The intent text is empty or longer than the 8 KiB cap."""

    code = "E_DOMAIN_INVALID_INTENT"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            "Invalid intent text: expected 1 to 8192 characters of "
            "non-blank UTF-8 text."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidOutputPath(DomainValidationError):
    """The output path escapes the configured root or contains '..' components."""

    code = "E_DOMAIN_INVALID_OUTPUT_PATH"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid output path {value!r}: must resolve to a location "
            "inside the configured root with no path-traversal components."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidPropertyConstraints(DomainValidationError):
    """The property constraints are internally inconsistent (e.g. min > max)."""

    code = "E_DOMAIN_INVALID_PROPERTY_CONSTRAINTS"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid property constraints {value!r}: constraint values "
            "are not internally consistent."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )


class InvalidSpecProperty(DomainValidationError):
    """A spec property has an invalid name, type, or item-type combination."""

    code = "E_DOMAIN_INVALID_SPEC_PROPERTY"

    def __init__(
        self,
        value: Any,
        *,
        cause: Exception | None = None,
        field_violations: list[FieldViolation] | None = None,
        **extra: Any,
    ) -> None:
        self.value = value
        msg = (
            f"Invalid spec property {value!r}: name, type, or item-type "
            "combination is not supported."
        )
        super().__init__(
            msg,
            field_violations=field_violations,
            cause=cause,
            value=value,
            **extra,
        )
