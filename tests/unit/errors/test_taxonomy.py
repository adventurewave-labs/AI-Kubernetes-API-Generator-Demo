"""Sanity tests for the typed error taxonomy (ADR-0016).

Verifies, for every concrete subclass of :class:`PlatformGeneratorError`:

* ``code`` is set to a non-empty, ``E_``-prefixed identifier.
* ``code`` values are unique across the hierarchy.
* ``__str__`` formats as ``"[<code>] <message>"``.
* ``recoverable`` is a bool, and the documented recoverable subclasses
  (``LlmUnavailable``, ``LlmRateLimited``) are flagged ``True``.

Subclasses with non-trivial constructors (``DomainValidationError``
subclasses, ``PrerequisiteMissing``) are exercised via type-specific
helpers below.
"""
from __future__ import annotations

from typing import Any

import pytest

from ai_platform_generator.domain import errors as err_pkg
from ai_platform_generator.domain.errors import (
    AmbiguousIntent,
    ArtifactGenerationError,
    ArtifactWriteFailed,
    ChecksumMismatch,
    ClusterCreationTimedOut,
    ClusterProvisioningError,
    ConfigurationError,
    CrdNotEstablished,
    DeploymentVerificationFailed,
    DomainValidationError,
    EmptySpec,
    IntentInterpretationError,
    InvalidConfigFile,
    InvalidGroup,
    InvalidKind,
    InvalidVersion,
    KubectlInvocationFailed,
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
    MissingApiKey,
    PersistenceError,
    PlatformGeneratorError,
    PostProcessingFailed,
    PrerequisiteMissing,
    ProvenanceCorrupted,
    ResourceVerificationFailed,
    TemplateRenderingError,
    UnsupportedSchema,
)

# ---------------------------------------------------------------------------
# Construction strategies for each concrete class
# ---------------------------------------------------------------------------


def _build(cls: type[PlatformGeneratorError]) -> PlatformGeneratorError:
    """Return a constructed instance of *cls*, choosing the right ctor shape."""
    if cls is PrerequisiteMissing:
        return PrerequisiteMissing(["kind"], {"kind": "brew install kind"})
    if cls is MissingApiKey:
        return MissingApiKey()
    if cls in {InvalidGroup, InvalidVersion, InvalidKind, UnsupportedSchema}:
        return cls("bogus")  # type: ignore[call-arg]
    if cls is EmptySpec:
        return EmptySpec()
    if issubclass(cls, DomainValidationError):
        return cls("boom")  # type: ignore[call-arg]
    return cls("boom")


# Every concrete subclass we expect to ship.
ALL_CONCRETE: tuple[type[PlatformGeneratorError], ...] = (
    # base bases (still concrete — instantiable)
    ConfigurationError,
    IntentInterpretationError,
    DomainValidationError,
    ArtifactGenerationError,
    ClusterProvisioningError,
    PersistenceError,
    # configuration
    MissingApiKey,
    InvalidConfigFile,
    PrerequisiteMissing,
    # intent
    LlmUnavailable,
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    AmbiguousIntent,
    # domain validation
    InvalidGroup,
    InvalidVersion,
    InvalidKind,
    EmptySpec,
    UnsupportedSchema,
    # artifact
    TemplateRenderingError,
    PostProcessingFailed,
    ChecksumMismatch,
    # cluster
    ClusterCreationTimedOut,
    KubectlInvocationFailed,
    ResourceVerificationFailed,
    CrdNotEstablished,
    DeploymentVerificationFailed,
    # persistence
    ArtifactWriteFailed,
    ProvenanceCorrupted,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", ALL_CONCRETE, ids=lambda c: c.__name__)
def test_each_concrete_class_has_a_valid_code(cls: type[PlatformGeneratorError]) -> None:
    assert isinstance(cls.code, str), f"{cls.__name__}.code must be str"
    assert cls.code, f"{cls.__name__}.code must be non-empty"
    assert cls.code.startswith("E_"), (
        f"{cls.__name__}.code must start with 'E_' (got {cls.code!r})"
    )


@pytest.mark.parametrize("cls", ALL_CONCRETE, ids=lambda c: c.__name__)
def test_each_concrete_class_has_a_bool_recoverable(
    cls: type[PlatformGeneratorError],
) -> None:
    assert isinstance(cls.recoverable, bool), (
        f"{cls.__name__}.recoverable must be bool"
    )


@pytest.mark.parametrize("cls", ALL_CONCRETE, ids=lambda c: c.__name__)
def test_str_format(cls: type[PlatformGeneratorError]) -> None:
    inst = _build(cls)
    rendered = str(inst)
    assert rendered.startswith(f"[{cls.code}]"), rendered
    assert inst.user_message in rendered


def test_codes_are_unique_across_concrete_hierarchy() -> None:
    seen: dict[str, str] = {}
    for cls in ALL_CONCRETE:
        if cls.code in seen:
            pytest.fail(
                f"Duplicate code {cls.code!r}: "
                f"{seen[cls.code]} vs {cls.__name__}"
            )
        seen[cls.code] = cls.__name__


def test_recoverable_classes_are_flagged() -> None:
    assert LlmUnavailable.recoverable is True
    assert LlmRateLimited.recoverable is True
    # Spot-check that non-recoverable defaults are preserved.
    assert MissingApiKey.recoverable is False
    assert InvalidGroup.recoverable is False
    assert ChecksumMismatch.recoverable is False


def test_cause_is_chained_via_dunder_cause() -> None:
    inner = ValueError("upstream")
    e = LlmUnavailable("LLM down", cause=inner, provider="openrouter")
    assert e.cause is inner
    assert e.__cause__ is inner
    assert e.extra == {"provider": "openrouter"}


def test_extra_kwargs_are_captured() -> None:
    e = KubectlInvocationFailed(
        "kubectl apply failed", exit_code=1, stderr_tail="boom"
    )
    assert e.extra == {"exit_code": 1, "stderr_tail": "boom"}


def test_prerequisite_missing_carries_tools_and_hints() -> None:
    p = PrerequisiteMissing(
        ["kind", "kubectl"],
        {"kind": "brew install kind", "kubectl": "brew install kubectl"},
    )
    assert p.missing_tools == ["kind", "kubectl"]
    assert p.install_hint == {
        "kind": "brew install kind",
        "kubectl": "brew install kubectl",
    }
    assert "kind" in p.user_message
    assert "kubectl" in p.user_message


def test_domain_validation_carries_field_violations() -> None:
    from ai_platform_generator.domain.errors import FieldViolation

    fv = FieldViolation(
        path="spec_properties.replicas.type",
        expected="int",
        actual="str",
        message="replicas.type must be 'integer', not 'string'",
    )
    e = InvalidKind("foo", field_violations=[fv])
    assert e.field_violations == [fv]


def test_inherited_recoverable_chain() -> None:
    # Subclasses inherit the parent's flag unless explicitly overridden.
    class CustomTimeout(ClusterProvisioningError):
        code = "E_CLUSTER_CUSTOM"

    assert CustomTimeout.recoverable is False  # default
    inst = CustomTimeout("hi")
    assert isinstance(inst, PlatformGeneratorError)


def test_public_re_exports() -> None:
    # Every concrete class must be importable from the package root.
    for cls in ALL_CONCRETE:
        assert hasattr(err_pkg, cls.__name__), cls.__name__
    # __all__ must be sorted alphabetically.
    assert err_pkg.__all__ == sorted(err_pkg.__all__)


def test_isinstance_chain_root() -> None:
    # Sanity: every concrete error is a PlatformGeneratorError.
    for cls in ALL_CONCRETE:
        inst: Any = _build(cls)
        assert isinstance(inst, PlatformGeneratorError)
        assert isinstance(inst, Exception)
