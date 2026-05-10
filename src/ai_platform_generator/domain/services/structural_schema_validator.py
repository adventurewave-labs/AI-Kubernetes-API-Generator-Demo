"""StructuralSchemaValidator domain service.

Enforces the Kubernetes structural-schema rules listed in
``docs/ddd/bounded-contexts/02-api-modelling.md`` section 8:

1. Every level has an explicit ``type``.
2. ``properties`` is used (not ``additionalProperties`` for arbitrary
   maps), unless explicitly opted in via
   ``x-kubernetes-preserve-unknown-fields``.
3. No ``oneOf`` / ``anyOf`` / ``not`` at any level (we keep it stricter
   than just the top level — Kubernetes itself only restricts the top
   level, but our subset is intentionally smaller for v1).
4. ``description`` is present on every named property.

Returns a list of :class:`FieldViolation`. Callers raise
:class:`UnsupportedSchema` (or ``IRRejected``) if the list is
non-empty.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_platform_generator.domain.aggregates.openapi_document import OpenAPIDocument
from ai_platform_generator.domain.errors import FieldViolation


class StructuralSchemaValidator:
    """Stateless validator for the IR's structural-schema invariants."""

    def validate(self, doc: OpenAPIDocument) -> list[FieldViolation]:
        """Return every structural-schema violation found in ``doc``."""
        violations: list[FieldViolation] = []

        for schema_name, schema in doc.schemas.items():
            self._walk(
                node=schema,
                path=f"components.schemas.{schema_name}",
                violations=violations,
                is_root=True,
                is_named_property=True,
            )

        return violations

    # ------------------------------------------------------------------
    # Internal: recursive walker
    # ------------------------------------------------------------------
    def _walk(
        self,
        *,
        node: Any,
        path: str,
        violations: list[FieldViolation],
        is_root: bool,
        is_named_property: bool,
    ) -> None:
        if not isinstance(node, Mapping):
            # A non-mapping at a structural position is itself a
            # violation, but we record it gracefully.
            violations.append(
                FieldViolation(
                    path=path,
                    expected="object schema",
                    actual=type(node).__name__,
                    message=f"expected an object schema at {path}, got {type(node).__name__}",
                )
            )
            return

        # Rule 1: every level has an explicit type.
        if "type" not in node:
            violations.append(
                FieldViolation(
                    path=f"{path}.type",
                    expected="explicit JSON-Schema type",
                    actual="missing",
                    message=f"every schema level must declare 'type' (at {path})",
                )
            )

        # Rule 3: no oneOf/anyOf/not anywhere.
        for forbidden in ("oneOf", "anyOf", "not"):
            if forbidden in node:
                violations.append(
                    FieldViolation(
                        path=f"{path}.{forbidden}",
                        expected="absent",
                        actual="present",
                        message=(
                            f"{forbidden!r} is not supported by the v1 structural "
                            f"schema (at {path})"
                        ),
                    )
                )

        # Rule 2: additionalProperties: true is forbidden unless
        # x-kubernetes-preserve-unknown-fields is set.
        ap = node.get("additionalProperties")
        if ap is True and not node.get("x-kubernetes-preserve-unknown-fields"):
            violations.append(
                FieldViolation(
                    path=f"{path}.additionalProperties",
                    expected="false or absent",
                    actual="true",
                    message=(
                        "'additionalProperties: true' requires "
                        "'x-kubernetes-preserve-unknown-fields' to be set "
                        f"(at {path})"
                    ),
                )
            )

        # Rule 4: description on every named property (not on the root
        # schema; that's optional). We treat the kind schema's child
        # ``properties`` entries as named properties.
        if is_named_property and not is_root and not node.get("description"):
            violations.append(
                FieldViolation(
                    path=f"{path}.description",
                    expected="non-empty description",
                    actual="missing",
                    message=f"named property at {path} is missing a description",
                )
            )

        # Recurse into properties.
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            for prop_name, prop_schema in properties.items():
                self._walk(
                    node=prop_schema,
                    path=f"{path}.properties.{prop_name}",
                    violations=violations,
                    is_root=False,
                    is_named_property=True,
                )

        # Recurse into items (arrays).
        items = node.get("items")
        if isinstance(items, Mapping):
            self._walk(
                node=items,
                path=f"{path}.items",
                violations=violations,
                is_root=False,
                is_named_property=False,
            )


__all__ = ["StructuralSchemaValidator"]
