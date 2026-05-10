"""RequestValidator domain service.

Implements the syntactic + lexical + semantic validation pipeline of
the Intent Interpretation context. See
``docs/ddd/bounded-contexts/01-intent-interpretation.md`` section 8 and
``docs/adr/0016-validation-pipeline-error-model.md``.

The validator's job is to **collect** every problem with a request so
the user can fix everything in a single iteration. It returns a list
of :class:`FieldViolation`; callers are expected to raise
:class:`CodegenRequestRejected` (or similar) if the list is non-empty.

Most of the lexical and per-property checks are already enforced by
the value-object constructors. Re-checking them here is intentional —
this service is the *aggregate-level* gate that produces structured
violations rather than raising on the first error.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import FieldViolation

_GROUP_RE = re.compile(r"^[a-z0-9.-]+\.[a-z0-9.-]+$")
_VERSION_RE = re.compile(r"^v\d+(?:(?:alpha|beta)\d+)?$")
_KIND_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_PROPERTY_NAME_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")


class RequestValidator:
    """Stateless aggregate-level validator for :class:`CodegenRequest`."""

    def validate_codegen_request(
        self, request: CodegenRequest
    ) -> list[FieldViolation]:
        """Return a list of every violation in ``request``.

        The aggregate's value objects already validate themselves at
        construction time, so by the time we see a ``CodegenRequest``
        most invariants are guaranteed. We still re-run the checks at
        the aggregate level so the validator can attach
        :class:`FieldViolation` paths the value objects can't see.
        """
        violations: list[FieldViolation] = []

        # ------------------------------------------------------------------
        # Syntactic stage — top-level shape (implicit since CodegenRequest
        # is typed; the value-object constructors guarantee `gvk` is a GVK).
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # Lexical stage — group / version / kind regex.
        # ------------------------------------------------------------------
        group_value = request.gvk.group.value
        if not _GROUP_RE.fullmatch(group_value):
            violations.append(
                FieldViolation(
                    path="gvk.group",
                    expected="reverse-DNS group (e.g. platform.example.com)",
                    actual=group_value,
                    message=f"gvk.group {group_value!r} does not match the expected pattern",
                )
            )

        version_value = request.gvk.version.value
        if not _VERSION_RE.fullmatch(version_value):
            violations.append(
                FieldViolation(
                    path="gvk.version",
                    expected="Kubernetes version (e.g. v1, v1alpha1, v2beta3)",
                    actual=version_value,
                    message=f"gvk.version {version_value!r} does not match the expected pattern",
                )
            )

        kind_value = request.gvk.kind.value
        if not _KIND_RE.fullmatch(kind_value):
            violations.append(
                FieldViolation(
                    path="gvk.kind",
                    expected="CamelCase identifier (e.g. PostgresCluster)",
                    actual=kind_value,
                    message=f"gvk.kind {kind_value!r} does not match the expected pattern",
                )
            )

        # ------------------------------------------------------------------
        # Semantic stage — spec_properties non-empty, unique names,
        # legal property names, no '..' in output_path.
        # ------------------------------------------------------------------
        if len(request.spec_properties) == 0:
            violations.append(
                FieldViolation(
                    path="spec_properties",
                    expected="at least one SpecProperty",
                    actual="empty tuple",
                    message="spec_properties must not be empty",
                )
            )

        seen: set[str] = set()
        for idx, prop in enumerate(request.spec_properties):
            if not _PROPERTY_NAME_RE.fullmatch(prop.name):
                violations.append(
                    FieldViolation(
                        path=f"spec_properties[{idx}].name",
                        expected="camelCase identifier",
                        actual=prop.name,
                        message=f"spec_property name {prop.name!r} is not a legal JSON identifier",
                    )
                )
            if prop.name in seen:
                violations.append(
                    FieldViolation(
                        path=f"spec_properties[{idx}].name",
                        expected="unique property name",
                        actual=prop.name,
                        message=f"duplicate spec property name {prop.name!r}",
                    )
                )
            seen.add(prop.name)

        # output_path: '..' check (already enforced by OutputPath, but we
        # also check the *string* form — defensive against future
        # bypasses).
        relative = PurePosixPath(str(request.output_path.relative))
        if any(part == ".." for part in relative.parts):
            violations.append(
                FieldViolation(
                    path="output_path.relative",
                    expected="path with no '..' components",
                    actual=str(request.output_path.relative),
                    message="output_path.relative must not contain '..' components",
                )
            )

        # description: non-blank.
        if not request.description.strip():
            violations.append(
                FieldViolation(
                    path="description",
                    expected="non-blank description",
                    actual=request.description,
                    message="description must be non-blank",
                )
            )

        return violations


__all__ = ["RequestValidator"]
