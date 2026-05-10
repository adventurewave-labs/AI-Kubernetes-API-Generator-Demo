"""PropertyType enum.

The set of JSON-Schema scalar/composite types we support for
``SpecProperty`` declarations.

See ``docs/ddd/04-tactical-design.md`` section 2.6 for the contract.
"""

from __future__ import annotations

from enum import StrEnum


class PropertyType(StrEnum):
    """Supported property types for a ``SpecProperty``.

    Values are the JSON-Schema type names so they can be serialised
    directly into the OpenAPI IR.
    """

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
