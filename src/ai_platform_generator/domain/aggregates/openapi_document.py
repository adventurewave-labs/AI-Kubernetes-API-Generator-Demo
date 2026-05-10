"""OpenAPIDocument aggregate root.

The intermediate representation (IR) of the API Modelling bounded
context. The IR is the single source of truth for every downstream
artefact generator (CRD, instance, Go controller, MCP server).

See ``docs/ddd/04-tactical-design.md`` section 4.2 and
``docs/ddd/bounded-contexts/02-api-modelling.md`` (especially
sections 6 and 7) for the full contract.

Determinism rules (section 7 of the API Modelling context) are the
load-bearing invariant: same input produces byte-identical IR. This
module owns:

* The IR builder (``OpenAPIDocument.from_request``).
* The deterministic serialiser (``OpenAPIDocument.serialise``).

Both are pure: no IO, no clocks, no randomness.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_platform_generator.domain.aggregates.codegen_request import (
    CodegenRequest,
    InvalidCodegenRequest,
)
from ai_platform_generator.domain.errors.domain_validation import DomainValidationError
from ai_platform_generator.domain.values import (
    GVK,
    Group,
    Kind,
    PropertyConstraints,
    PropertyType,
    SpecProperty,
    Version,
)

#: Stable IR schema-version stamp. Bump on breaking changes.
IR_VERSION = "1.0.0"

#: OpenAPI version we always emit. Kubernetes accepts 3.0.x for CRDs.
OPENAPI_VERSION = "3.0.0"


class InvalidOpenAPIDocument(DomainValidationError):
    """The :class:`OpenAPIDocument` aggregate failed an invariant check."""

    code = "E_DOMAIN_INVALID_OPENAPI_DOCUMENT"


# ---------------------------------------------------------------------------
# Pydantic value objects (cross-JSON-boundary types)
# ---------------------------------------------------------------------------


class OpenApiInfo(BaseModel):
    """The ``info`` block of an OpenAPI document.

    Frozen because it crosses serialisation boundaries (and is part of
    the IR's identity).
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    title: str
    version: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical lex-sorted dict form of this info block."""
        return _sorted_dict(self.model_dump(mode="json", exclude_none=True))


class JsonSchema(BaseModel):
    """A recursive JSON-Schema fragment.

    We deliberately accept arbitrary keys (``extra="allow"``) because the
    OpenAPI/JSON-Schema vocabulary is large and we need round-trip
    fidelity. Validation of *which* keys are valid for a structural
    schema is the responsibility of
    :class:`StructuralSchemaValidator`, not of this value object.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    type: str | None = None
    properties: dict[str, Any] | None = None
    required: list[str] | None = None
    items: dict[str, Any] | None = None
    description: str | None = None
    format: str | None = None
    enum: list[Any] | None = None
    pattern: str | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    # Length constraints aliased to camelCase for OpenAPI:
    minLength: int | None = Field(default=None)
    maxLength: int | None = Field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical lex-sorted dict form."""
        return _sorted_dict(self.model_dump(mode="json", exclude_none=True))


# ---------------------------------------------------------------------------
# OpenAPIDocument aggregate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OpenAPIDocument:
    """The aggregate root of the API Modelling context.

    Parameters
    ----------
    info:
        The OpenAPI ``info`` block.
    schemas:
        ``components.schemas`` keyed by schema name. The dict is wrapped
        in a :class:`types.MappingProxyType` so the aggregate is
        effectively immutable.
    paths:
        ``paths`` (empty for CRDs but kept for forward compatibility).
    extensions:
        Additional ``x-*`` extensions stored at the root.

    The aggregate's identity is the (sorted) byte representation of
    :meth:`to_dict`. Two documents with the same content are equal even
    if their dict orderings differ at construction time.
    """

    info: OpenApiInfo
    schemas: Mapping[str, Any]
    paths: Mapping[str, Mapping[str, Any]]
    extensions: Mapping[str, Any]

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not isinstance(self.info, OpenApiInfo):
            raise InvalidOpenAPIDocument(
                f"info must be an OpenApiInfo, got {type(self.info)!r}"
            )
        if not isinstance(self.schemas, Mapping):
            raise InvalidOpenAPIDocument(
                f"schemas must be a Mapping, got {type(self.schemas)!r}"
            )
        if not isinstance(self.paths, Mapping):
            raise InvalidOpenAPIDocument(
                f"paths must be a Mapping, got {type(self.paths)!r}"
            )
        if not isinstance(self.extensions, Mapping):
            raise InvalidOpenAPIDocument(
                f"extensions must be a Mapping, got {type(self.extensions)!r}"
            )

        # Wrap mappings in MappingProxyType for immutability.
        if not isinstance(self.schemas, MappingProxyType):
            object.__setattr__(
                self, "schemas", MappingProxyType(dict(self.schemas))
            )
        if not isinstance(self.paths, MappingProxyType):
            object.__setattr__(
                self, "paths", MappingProxyType(dict(self.paths))
            )
        if not isinstance(self.extensions, MappingProxyType):
            object.__setattr__(
                self, "extensions", MappingProxyType(dict(self.extensions))
            )

    # ------------------------------------------------------------------
    # Derived attributes
    # ------------------------------------------------------------------
    @property
    def gvk(self) -> GVK:
        """Recover the GVK round-tripped through ``info.x-kubernetes-gvk``.

        Raises
        ------
        InvalidOpenAPIDocument
            If the extension is missing or malformed.
        """
        ext = self.info.model_dump(mode="json").get("x-kubernetes-gvk")
        if not isinstance(ext, Mapping):
            raise InvalidOpenAPIDocument(
                "OpenAPIDocument.info is missing the 'x-kubernetes-gvk' extension"
            )
        try:
            return GVK(
                group=Group(str(ext["group"])),
                version=Version(str(ext["version"])),
                kind=Kind(str(ext["kind"])),
            )
        except KeyError as exc:
            raise InvalidOpenAPIDocument(
                f"x-kubernetes-gvk extension missing key: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # IR builder (factory)
    # ------------------------------------------------------------------
    @classmethod
    def from_request(cls, request: CodegenRequest) -> OpenAPIDocument:
        """Build an OpenAPI IR from a validated ``CodegenRequest``.

        Mapping rules per ``docs/ddd/bounded-contexts/02-api-modelling.md``
        section 6. Determinism per section 7.
        """
        if not isinstance(request, CodegenRequest):
            raise InvalidCodegenRequest(
                f"from_request expects a CodegenRequest, got {type(request)!r}"
            )

        kind_name = request.gvk.kind.value

        # info block.
        info = OpenApiInfo.model_validate(
            {
                "title": f"{kind_name} API",
                "version": request.gvk.version.value,
                "description": request.description,
                "x-platform-generator-ir": IR_VERSION,
                "x-kubernetes-gvk": {
                    "group": request.gvk.group.value,
                    "version": request.gvk.version.value,
                    "kind": kind_name,
                },
            }
        )

        # spec.properties / spec.required.
        spec_props: dict[str, dict[str, Any]] = {}
        required: list[str] = []
        for prop in request.spec_properties:
            spec_props[prop.name] = _spec_property_to_schema(prop)
            # All explicitly-declared properties are required by default.
            required.append(prop.name)

        spec_schema: dict[str, Any] = {
            "type": "object",
            "description": f"Specification of the desired {kind_name}.",
            "properties": _sorted_dict(spec_props),
            "required": sorted(required),
        }

        kind_schema: dict[str, Any] = {
            "type": "object",
            "description": f"Schema for the {kind_name} resource.",
            "required": ["apiVersion", "kind", "metadata", "spec"],
            "properties": {
                "apiVersion": {
                    "type": "string",
                    "description": (
                        f"API version, e.g. {request.gvk.group.value}/"
                        f"{request.gvk.version.value}"
                    ),
                },
                "kind": {
                    "type": "string",
                    "description": f"Resource kind, e.g. {kind_name}",
                },
                "metadata": {
                    "type": "object",
                    "description": "Standard Kubernetes object metadata.",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the resource.",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace of the resource.",
                        },
                    },
                },
                "spec": spec_schema,
                "status": {
                    "type": "object",
                    "description": f"Observed state of the {kind_name}.",
                    "properties": {},
                },
            },
        }

        schemas = {kind_name: kind_schema}

        return cls(
            info=info,
            schemas=MappingProxyType(schemas),
            paths=MappingProxyType({}),
            extensions=MappingProxyType({}),
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Return the canonical, lexicographically-sorted dict form.

        Determinism guarantees: identical ``CodegenRequest`` inputs
        produce byte-identical ``to_dict()`` output (Python's dict
        preserves insertion order, but :func:`json.dumps` with
        ``sort_keys=True`` re-sorts keys at every level — and we sort
        at this level too, so equality comparison is also stable).
        """
        info_dict = self.info.to_dict()
        # Schemas: each schema is sorted recursively.
        schemas_dict = {
            name: _sorted(schema) for name, schema in self.schemas.items()
        }
        out: dict[str, Any] = {
            "openapi": OPENAPI_VERSION,
            "info": info_dict,
            "paths": _sorted(dict(self.paths)),
            "components": {
                "schemas": _sorted_dict(schemas_dict),
            },
        }
        if self.extensions:
            for k, v in self.extensions.items():
                out[k] = _sorted(v) if isinstance(v, (Mapping, list)) else v
        return _sorted_dict(out)

    def serialise(self, indent: int = 2) -> bytes:
        """Serialise to UTF-8 JSON with sorted keys and a trailing newline.

        This is the *only* path that emits IR bytes. Any caller that
        needs IR text must go through this method to get the
        determinism guarantees.
        """
        text = json.dumps(self.to_dict(), indent=indent, sort_keys=True)
        return (text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _spec_property_to_schema(prop: SpecProperty) -> dict[str, Any]:
    """Map a single :class:`SpecProperty` to a JSON-Schema fragment."""
    schema: dict[str, Any]

    if prop.type is PropertyType.STRING:
        schema = {"type": "string"}
    elif prop.type is PropertyType.INTEGER:
        schema = {"type": "integer", "format": "int32"}
    elif prop.type is PropertyType.NUMBER:
        schema = {"type": "number", "format": "double"}
    elif prop.type is PropertyType.BOOLEAN:
        schema = {"type": "boolean"}
    elif prop.type is PropertyType.ARRAY:
        # item_type is enforced by SpecProperty.__post_init__.
        assert prop.item_type is not None
        schema = {
            "type": "array",
            "items": _scalar_type_to_schema(prop.item_type),
            "x-kubernetes-list-type": "atomic",
        }
    elif prop.type is PropertyType.OBJECT:
        schema = {
            "type": "object",
            "x-kubernetes-preserve-unknown-fields": False,
        }
    else:  # pragma: no cover - defensive
        raise InvalidOpenAPIDocument(
            f"unsupported PropertyType for IR: {prop.type!r}"
        )

    # Constraints are merged in. Format from the property type takes
    # precedence over a user-supplied format only if user did not
    # override it.
    _merge_constraints(schema, prop.constraints)

    description = prop.description.strip() or f"Specification for {prop.name}"
    schema["description"] = description

    return _sorted_dict(schema)


def _scalar_type_to_schema(t: PropertyType) -> dict[str, Any]:
    """Map a scalar :class:`PropertyType` to a JSON-Schema fragment."""
    if t is PropertyType.STRING:
        return {"type": "string"}
    if t is PropertyType.INTEGER:
        return {"type": "integer", "format": "int32"}
    if t is PropertyType.NUMBER:
        return {"type": "number", "format": "double"}
    if t is PropertyType.BOOLEAN:
        return {"type": "boolean"}
    raise InvalidOpenAPIDocument(  # pragma: no cover - defensive
        f"non-scalar type {t!r} cannot be an array item type"
    )


def _merge_constraints(schema: dict[str, Any], c: PropertyConstraints) -> None:
    """Merge ``PropertyConstraints`` keys into a JSON-Schema ``schema`` dict."""
    if c.minimum is not None:
        schema["minimum"] = c.minimum
    if c.maximum is not None:
        schema["maximum"] = c.maximum
    if c.min_length is not None:
        schema["minLength"] = c.min_length
    if c.max_length is not None:
        schema["maxLength"] = c.max_length
    if c.pattern is not None:
        schema["pattern"] = c.pattern
    if c.enum is not None:
        schema["enum"] = sorted(c.enum)
    if c.format is not None:
        schema["format"] = c.format


def _sorted(value: Any) -> Any:
    """Recursively return a lexicographically-sorted version of ``value``.

    Dicts are sorted by key. Lists are returned unchanged (their
    semantic order matters: e.g. ``required`` is already sorted by the
    caller, ``enum`` is already sorted by the caller, etc.). Scalars
    pass through.
    """
    if isinstance(value, Mapping):
        return {k: _sorted(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    return value


def _sorted_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Like :func:`_sorted` but typed for ``dict`` inputs."""
    return {k: _sorted(value[k]) for k in sorted(value.keys())}
