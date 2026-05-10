"""CodegenRequest aggregate root.

The output of the **Intent Interpretation** bounded context and the
input to the **API Modelling** context. See
``docs/ddd/04-tactical-design.md`` section 4.1 and
``docs/ddd/bounded-contexts/01-intent-interpretation.md`` for the
contract.

Notes
-----
* The aggregate is fully immutable. To "modify" a request, produce a new
  one via the ``with_*`` builders.
* ``spec_properties`` is stored as a tuple (rather than ``frozenset``)
  because we need a stable iteration order for deterministic IR
  serialisation. Uniqueness of names is enforced in ``__post_init__``.
* ``to_dict`` / ``from_dict`` round-trip the aggregate to a plain dict so
  it can be persisted in the provenance manifest, an ``RunRepository``
  log, or a re-run snapshot, without the aggregate ever leaking into the
  filesystem layer directly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_platform_generator.domain.errors import (
    EmptySpec,
    InvalidSpecProperty,
)
from ai_platform_generator.domain.errors.domain_validation import DomainValidationError
from ai_platform_generator.domain.values import (
    GVK,
    Group,
    Kind,
    OutputPath,
    PropertyConstraints,
    PropertyType,
    ProviderMode,
    SpecProperty,
    Version,
)

#: Maximum description length, post-strip.
_MAX_DESCRIPTION = 1024


class InvalidCodegenRequest(DomainValidationError):
    """The :class:`CodegenRequest` aggregate failed an invariant check."""

    code = "E_DOMAIN_INVALID_CODEGEN_REQUEST"


@dataclass(frozen=True, slots=True)
class CodegenRequest:
    """The validated, structured user request for one generation run.

    Parameters
    ----------
    gvk:
        The Kubernetes group/version/kind triple this request will produce.
    spec_properties:
        A tuple of :class:`SpecProperty` declarations. Order-stable so
        downstream serialisers (the IR, the CRD) emit byte-identical
        output for byte-identical inputs. Names must be unique.
    output_path:
        Where on disk the bundle will be written.
    description:
        Free-form description carried into ``info.description`` of the
        OpenAPI document. Non-blank, ≤ 1024 characters after strip.
    provider_mode:
        Which provider mode produced the request (``LIVE`` vs ``DEMO``).
    """

    gvk: GVK
    spec_properties: tuple[SpecProperty, ...]
    output_path: OutputPath
    description: str
    provider_mode: ProviderMode

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        # gvk: typed by construction, but defensively check.
        if not isinstance(self.gvk, GVK):
            raise InvalidCodegenRequest(
                f"gvk must be a GVK, got {type(self.gvk)!r}"
            )
        if not isinstance(self.output_path, OutputPath):
            raise InvalidCodegenRequest(
                f"output_path must be an OutputPath, got {type(self.output_path)!r}"
            )
        if not isinstance(self.provider_mode, ProviderMode):
            raise InvalidCodegenRequest(
                f"provider_mode must be a ProviderMode, got {type(self.provider_mode)!r}"
            )

        # spec_properties: non-empty, all SpecProperty, unique names.
        if not isinstance(self.spec_properties, tuple):
            raise InvalidCodegenRequest(
                "spec_properties must be a tuple (got "
                f"{type(self.spec_properties)!r})"
            )
        if len(self.spec_properties) == 0:
            raise EmptySpec()
        seen: set[str] = set()
        for prop in self.spec_properties:
            if not isinstance(prop, SpecProperty):
                raise InvalidSpecProperty(
                    f"spec_properties entry must be a SpecProperty, got "
                    f"{type(prop)!r}"
                )
            if prop.name in seen:
                raise InvalidCodegenRequest(
                    f"duplicate spec property name {prop.name!r}"
                )
            seen.add(prop.name)

        # description: non-blank, length-bounded post-strip.
        if not isinstance(self.description, str):
            raise InvalidCodegenRequest(
                f"description must be a str, got {type(self.description)!r}"
            )
        stripped = self.description.strip()
        if not stripped:
            raise InvalidCodegenRequest("description must be non-blank")
        if len(stripped) > _MAX_DESCRIPTION:
            raise InvalidCodegenRequest(
                "description must be at most "
                f"{_MAX_DESCRIPTION} characters after stripping, got "
                f"{len(stripped)}"
            )

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def with_provider_mode(self, mode: ProviderMode) -> CodegenRequest:
        """Return a copy with a new :class:`ProviderMode`."""
        return CodegenRequest(
            gvk=self.gvk,
            spec_properties=self.spec_properties,
            output_path=self.output_path,
            description=self.description,
            provider_mode=mode,
        )

    def with_output_path(self, path: OutputPath) -> CodegenRequest:
        """Return a copy with a new :class:`OutputPath`."""
        return CodegenRequest(
            gvk=self.gvk,
            spec_properties=self.spec_properties,
            output_path=path,
            description=self.description,
            provider_mode=self.provider_mode,
        )

    def with_description(self, description: str) -> CodegenRequest:
        """Return a copy with a new ``description`` (validated)."""
        return CodegenRequest(
            gvk=self.gvk,
            spec_properties=self.spec_properties,
            output_path=self.output_path,
            description=description,
            provider_mode=self.provider_mode,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Serialise the aggregate to a plain JSON-compatible dict.

        Property order in ``spec_properties`` is preserved verbatim — it
        is part of the aggregate's identity for golden tests.
        """
        return {
            "gvk": {
                "group": self.gvk.group.value,
                "version": self.gvk.version.value,
                "kind": self.gvk.kind.value,
            },
            "spec_properties": [
                _spec_property_to_dict(prop) for prop in self.spec_properties
            ],
            "output_path": {
                "root": str(self.output_path.root),
                "relative": str(self.output_path.relative),
            },
            "description": self.description,
            "provider_mode": self.provider_mode.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CodegenRequest:
        """Reconstruct a :class:`CodegenRequest` from :meth:`to_dict` output.

        Validation is delegated to the value objects' constructors; any
        invariant violation raises a :class:`DomainValidationError`.
        """
        if not isinstance(data, Mapping):
            raise InvalidCodegenRequest(
                f"from_dict expects a Mapping, got {type(data)!r}"
            )
        gvk_data = data.get("gvk")
        if not isinstance(gvk_data, Mapping):
            raise InvalidCodegenRequest("from_dict: 'gvk' must be a mapping")
        gvk = GVK(
            group=Group(str(gvk_data["group"])),
            version=Version(str(gvk_data["version"])),
            kind=Kind(str(gvk_data["kind"])),
        )

        spec_props_data = data.get("spec_properties")
        if not isinstance(spec_props_data, Iterable):
            raise InvalidCodegenRequest(
                "from_dict: 'spec_properties' must be iterable"
            )
        spec_properties = tuple(
            _spec_property_from_dict(item) for item in spec_props_data
        )

        op_data = data.get("output_path")
        if not isinstance(op_data, Mapping):
            raise InvalidCodegenRequest(
                "from_dict: 'output_path' must be a mapping"
            )
        output_path = OutputPath(
            root=Path(str(op_data["root"])),
            relative=Path(str(op_data["relative"])),
        )

        description = str(data.get("description", ""))
        provider_mode = ProviderMode(str(data.get("provider_mode", "live")))

        return cls(
            gvk=gvk,
            spec_properties=spec_properties,
            output_path=output_path,
            description=description,
            provider_mode=provider_mode,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spec_property_to_dict(prop: SpecProperty) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": prop.name,
        "type": prop.type.value,
        "description": prop.description,
        "constraints": _constraints_to_dict(prop.constraints),
    }
    if prop.item_type is not None:
        out["item_type"] = prop.item_type.value
    return out


def _constraints_to_dict(c: PropertyConstraints) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if c.minimum is not None:
        out["minimum"] = c.minimum
    if c.maximum is not None:
        out["maximum"] = c.maximum
    if c.min_length is not None:
        out["min_length"] = c.min_length
    if c.max_length is not None:
        out["max_length"] = c.max_length
    if c.pattern is not None:
        out["pattern"] = c.pattern
    if c.enum is not None:
        out["enum"] = list(c.enum)
    if c.format is not None:
        out["format"] = c.format
    return out


def _spec_property_from_dict(data: Any) -> SpecProperty:
    if not isinstance(data, Mapping):
        raise InvalidCodegenRequest(
            f"spec_property entry must be a mapping, got {type(data)!r}"
        )
    constraints_data = data.get("constraints", {}) or {}
    if not isinstance(constraints_data, Mapping):
        raise InvalidCodegenRequest(
            "spec_property.constraints must be a mapping"
        )
    enum_val = constraints_data.get("enum")
    constraints = PropertyConstraints(
        minimum=constraints_data.get("minimum"),
        maximum=constraints_data.get("maximum"),
        min_length=constraints_data.get("min_length"),
        max_length=constraints_data.get("max_length"),
        pattern=constraints_data.get("pattern"),
        enum=tuple(enum_val) if enum_val is not None else None,
        format=constraints_data.get("format"),
    )
    item_type_raw = data.get("item_type")
    item_type = PropertyType(item_type_raw) if item_type_raw is not None else None
    return SpecProperty(
        name=str(data["name"]),
        type=PropertyType(str(data["type"])),
        description=str(data["description"]),
        constraints=constraints,
        item_type=item_type,
    )
