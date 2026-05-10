"""SpecProperty value object.

A single named property under ``spec`` in a generated CRD.

See ``docs/ddd/04-tactical-design.md`` section 2.5 for the contract.

Notes
-----
* Nested object schemas (``type == OBJECT`` with sub-properties) are
  **out of scope for v1**: ``OBJECT`` is accepted as a leaf type but
  has no nested structure here. Future iterations may introduce a
  ``NestedSchema`` value object.
* For ``ARRAY``, ``item_type`` is required and must be a scalar
  (string / integer / number / boolean) — arrays of arrays and arrays
  of objects are explicitly rejected for v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_platform_generator.domain.errors import InvalidSpecProperty
from ai_platform_generator.domain.values.property_constraints import PropertyConstraints
from ai_platform_generator.domain.values.property_type import PropertyType

_NAME_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")

_SCALAR_TYPES: frozenset[PropertyType] = frozenset(
    {
        PropertyType.STRING,
        PropertyType.INTEGER,
        PropertyType.NUMBER,
        PropertyType.BOOLEAN,
    }
)


@dataclass(frozen=True, slots=True)
class SpecProperty:
    """An immutable spec property declaration.

    Parameters
    ----------
    name:
        camelCase JSON identifier matching ``^[a-z][A-Za-z0-9]*$``.
    type:
        The :class:`PropertyType` of this property.
    description:
        Human-readable description; must be non-empty after stripping.
    constraints:
        :class:`PropertyConstraints`; pass ``PropertyConstraints()`` for
        no constraints.
    item_type:
        Required iff ``type == PropertyType.ARRAY``. Must itself be a
        scalar type — nested arrays / objects are rejected for v1.
    """

    name: str
    type: PropertyType
    description: str
    constraints: PropertyConstraints
    item_type: PropertyType | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME_RE.fullmatch(self.name):
            raise InvalidSpecProperty(
                f"name {self.name!r} is not a valid camelCase JSON identifier"
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidSpecProperty(
                f"description for property {self.name!r} must be non-empty"
            )
        if not isinstance(self.type, PropertyType):
            raise InvalidSpecProperty(
                f"type for property {self.name!r} must be a PropertyType"
            )
        if self.type is PropertyType.ARRAY:
            if self.item_type is None:
                raise InvalidSpecProperty(
                    f"array property {self.name!r} requires an item_type"
                )
            if self.item_type not in _SCALAR_TYPES:
                raise InvalidSpecProperty(
                    f"array property {self.name!r} item_type must be a scalar type, "
                    f"got {self.item_type}"
                )
        else:
            if self.item_type is not None:
                raise InvalidSpecProperty(
                    f"non-array property {self.name!r} must not set item_type"
                )
