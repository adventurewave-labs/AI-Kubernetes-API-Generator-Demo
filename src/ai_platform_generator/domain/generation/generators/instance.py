"""Instance-YAML artefact generator.

Emits a single starter manifest of the IR's CRD kind — i.e. a "fill me
in" example a user can ``kubectl apply``. Every spec property gets a
deterministic placeholder value so the output is byte-stable across
runs, and so the rendered YAML is structurally valid against the CRD
schema produced by :class:`CrdYamlGenerator`.

Mapping rules per ``docs/ddd/bounded-contexts/03-artifact-generation.md``
§6.2.1:

* ``apiVersion`` is ``<group>/<version>`` from the GVK.
* ``kind`` is the GVK kind verbatim.
* ``metadata.name`` is ``my-<kindLower>-instance``.
* ``metadata.namespace`` is ``default``.
* ``spec`` contains a placeholder for every property in the IR:

  * string  → first enum value (if any), else the constraint
              ``default``, else the literal ``"example"``.
  * integer → ``minimum`` (if any), else ``1``.
  * number  → ``minimum`` (if any) as a float, else ``1.0``.
  * boolean → ``true``.
  * array   → a single-element list of the item-type's placeholder.
  * object  → ``{}``.

Determinism
-----------
* Placeholders depend only on the IR; no clock, no randomness.
* ``spec`` keys are emitted in **lexicographic order** (we sort them
  before dumping) so dict insertion-order quirks cannot leak through.
* PyYAML is invoked with ``sort_keys=False`` so we control ordering;
  reusing the :class:`_StableDumper` from :mod:`crd` keeps null/bool
  formatting consistent with the sibling generator.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.generators.crd import _StableDumper
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile

#: Default namespace used for the example manifest.
_DEFAULT_NAMESPACE = "default"

#: Fallback placeholder for plain strings (no enum, no default).
_STRING_PLACEHOLDER = "example"


@register_generator
class InstanceYamlGenerator(ArtifactGenerator):
    """Emit ``<kindLower>.instance.yaml`` — a starter custom-resource manifest."""

    name = "instance"
    artefact_type = ArtifactType.INSTANCE

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"InstanceYamlGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        if not ir.schemas:
            raise ArtifactGenerationError(
                "InstanceYamlGenerator: IR has no schemas — refusing to "
                "emit an empty instance"
            )
        try:
            _ = ir.gvk
        except Exception as exc:
            raise ArtifactGenerationError(
                f"InstanceYamlGenerator: IR has no GVK extension: {exc}"
            ) from exc

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        kind_lower = ir.gvk.kind.value.lower()
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / f"{kind_lower}.instance.yaml",),
            metadata={
                "kind": ir.gvk.kind.value,
                "kind_lower": kind_lower,
                "doc": _build_instance_dict(ir),
            },
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        doc = plan.metadata["doc"]
        if not isinstance(doc, dict):  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"InstanceYamlGenerator: plan metadata['doc'] must be a dict, "
                f"got {type(doc).__name__}"
            )
        text = yaml.dump(
            doc,
            Dumper=_StableDumper,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=120,
            allow_unicode=True,
        )
        payload = text.encode("utf-8")
        return (_RenderedFile(path=plan.target_files[0], payload=payload),)


# ----------------------------------------------------------------------
# Pure builders (module-private)
# ----------------------------------------------------------------------
def _build_instance_dict(ir: OpenAPIDocument) -> dict[str, Any]:
    """Construct the example custom-resource dict from the IR (no I/O)."""
    gvk = ir.gvk
    kind_value = gvk.kind.value
    kind_lower = kind_value.lower()

    kind_schema = ir.schemas[kind_value]
    if not isinstance(kind_schema, Mapping):
        raise ArtifactGenerationError(
            f"InstanceYamlGenerator: kind schema for {kind_value!r} must "
            f"be a mapping, got {type(kind_schema).__name__}"
        )
    spec_schema = kind_schema.get("properties", {}).get("spec")
    if not isinstance(spec_schema, Mapping):
        raise ArtifactGenerationError(
            f"InstanceYamlGenerator: kind schema for {kind_value!r} is "
            "missing a properties.spec block"
        )

    spec_props_raw = spec_schema.get("properties") or {}
    if not isinstance(spec_props_raw, Mapping):
        raise ArtifactGenerationError(
            "InstanceYamlGenerator: spec.properties must be a mapping, "
            f"got {type(spec_props_raw).__name__}"
        )

    spec: dict[str, Any] = {}
    for name in sorted(spec_props_raw.keys()):
        prop_schema = spec_props_raw[name]
        if not isinstance(prop_schema, Mapping):
            raise ArtifactGenerationError(
                f"InstanceYamlGenerator: spec.properties[{name!r}] must "
                f"be a mapping, got {type(prop_schema).__name__}"
            )
        spec[name] = _placeholder_for(dict(prop_schema))

    return {
        "apiVersion": gvk.api_version,
        "kind": kind_value,
        "metadata": {
            "name": f"my-{kind_lower}-instance",
            "namespace": _DEFAULT_NAMESPACE,
        },
        "spec": spec,
    }


def _placeholder_for(prop_schema: Mapping[str, Any]) -> Any:
    """Return a deterministic placeholder for a single JSON-Schema fragment.

    The mapping prefers explicit hints from the schema:

    1. ``default`` (an explicit constraint set by the IR builder).
    2. ``enum`` (first value, in the order the IR captured them).
    3. ``minimum`` (numeric lower bound).

    Falling through to a per-type literal otherwise.
    """
    if "default" in prop_schema:
        return prop_schema["default"]

    type_name = prop_schema.get("type")
    enum = prop_schema.get("enum")
    minimum = prop_schema.get("minimum")

    if type_name == "string":
        if isinstance(enum, list) and enum:
            return enum[0]
        return _STRING_PLACEHOLDER

    if type_name == "integer":
        if isinstance(minimum, (int, float)):
            return int(minimum)
        return 1

    if type_name == "number":
        if isinstance(minimum, (int, float)):
            return float(minimum)
        return 1.0

    if type_name == "boolean":
        return True

    if type_name == "array":
        items = prop_schema.get("items")
        if isinstance(items, Mapping):
            return [_placeholder_for(dict(items))]
        # Unknown items shape — emit an empty list rather than guess.
        return []

    if type_name == "object":
        # Nested objects are out of scope for v1; emit an empty mapping.
        return {}

    # Unknown / missing type — keep the slot present but null-valued so
    # the user can see that something was declared.
    return None


__all__ = ["InstanceYamlGenerator"]
