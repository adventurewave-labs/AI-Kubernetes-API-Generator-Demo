"""CRD (``CustomResourceDefinition``) artefact generator.

Maps an :class:`OpenAPIDocument` IR to a single Kubernetes
``apiextensions.k8s.io/v1`` CRD manifest. The mapping is the one
prescribed by ADR-0005 and
``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.2.1:

* ``metadata.name`` is the GVK's ``crd_name`` (``<plural>.<group>``).
* ``spec.group`` is the GVK's group, ``spec.scope`` is ``Namespaced``.
* ``spec.names`` is derived from :class:`Kind` (``kind`` / ``listKind``
  / ``plural`` / ``singular`` / empty ``shortNames``).
* ``spec.versions[0]`` carries the version + the structural schema.
  The schema is the IR's per-Kind schema with the Kubernetes-injected
  top-level fields (``apiVersion``, ``kind``, ``metadata``) stripped
  out, since the API server fills those in. ``spec`` and ``status``
  flow through verbatim.
* ``subresources.status`` is always present (we always emit a status
  subresource — the Go controller writes to it).

Determinism
-----------
Output is byte-stable for byte-stable input:

* Property dicts at every level are emitted in **lexicographic key
  order** (we recursively sort before dumping).
* ``required`` arrays are sorted by the IR builder; we re-sort
  defensively here in case future IR shapes regress on that promise.
* PyYAML is invoked with ``sort_keys=False, default_flow_style=False``
  so we control ordering ourselves; a custom :class:`_StableDumper`
  emits ``null`` (rather than ``~``) for ``None`` and forces the
  unquoted ``true`` / ``false`` lowercase canonical form for booleans.

No template engine is used — the document is simple enough that
direct dict-dump beats Jinja2 on idempotency and review-ability.
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
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile

#: ``apiVersion`` for the CRD manifest itself (the meta-API).
_CRD_API_VERSION = "apiextensions.k8s.io/v1"

#: ``kind`` for the CRD manifest itself.
_CRD_KIND = "CustomResourceDefinition"

#: Default scope for v1 — future ADR may parametrise.
_CRD_SCOPE = "Namespaced"

#: Top-level keys injected by the Kubernetes API server. We strip them
#: from the IR's per-Kind schema before placing it under
#: ``spec.versions[0].schema.openAPIV3Schema`` because the API server
#: validates these centrally and rejects redundant copies.
_INJECTED_TOPLEVEL_KEYS: frozenset[str] = frozenset(
    {"apiVersion", "kind", "metadata"}
)


class _StableDumper(yaml.SafeDumper):
    """PyYAML dumper tuned for Kubernetes-friendly, byte-stable output.

    * ``None`` is rendered as ``null`` (rather than the empty string or
      ``~``) — Kubernetes manifests universally use ``null``.
    * Booleans render as canonical lowercase ``true`` / ``false``.
    * Indentation is fixed at 2; flow-style is disabled at the
      top-level via the dump call site.
    """


def _represent_none(dumper: yaml.SafeDumper, _data: Any) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def _represent_bool(dumper: yaml.SafeDumper, data: bool) -> yaml.Node:
    return dumper.represent_scalar(
        "tag:yaml.org,2002:bool", "true" if data else "false"
    )


_StableDumper.add_representer(type(None), _represent_none)
_StableDumper.add_representer(bool, _represent_bool)


@register_generator
class CrdYamlGenerator(ArtifactGenerator):
    """Emit ``<kindLower>.crd.yaml`` — the CRD manifest for the IR's GVK."""

    name = "crd"
    artefact_type = ArtifactType.CRD

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"CrdYamlGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        if not ir.schemas:
            raise ArtifactGenerationError(
                "CrdYamlGenerator: IR has no schemas — refusing to emit "
                "an empty CRD"
            )
        # GVK must round-trip — raises InvalidOpenAPIDocument if the
        # ``x-kubernetes-gvk`` extension is missing.
        try:
            _ = ir.gvk
        except Exception as exc:
            raise ArtifactGenerationError(
                f"CrdYamlGenerator: IR has no GVK extension: {exc}"
            ) from exc

        kind_name = ir.gvk.kind.value
        if kind_name not in ir.schemas:
            raise ArtifactGenerationError(
                f"CrdYamlGenerator: IR is missing the schema for kind "
                f"{kind_name!r} (have {sorted(ir.schemas)!r})"
            )

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        kind_lower = ir.gvk.kind.value.lower()
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / f"{kind_lower}.crd.yaml",),
            metadata={
                "kind": ir.gvk.kind.value,
                "kind_lower": kind_lower,
                "doc": _build_crd_dict(ir),
            },
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        doc = plan.metadata["doc"]
        if not isinstance(doc, dict):  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"CrdYamlGenerator: plan metadata['doc'] must be a dict, "
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
def _build_crd_dict(ir: OpenAPIDocument) -> dict[str, Any]:
    """Construct the CRD manifest dict from the IR (no I/O)."""
    gvk = ir.gvk
    kind_value = gvk.kind.value

    kind_schema = ir.schemas[kind_value]
    if not isinstance(kind_schema, Mapping):
        raise ArtifactGenerationError(
            f"CrdYamlGenerator: kind schema for {kind_value!r} must be a "
            f"mapping, got {type(kind_schema).__name__}"
        )
    structural = _strip_injected_keys(dict(kind_schema))

    # ``metadata`` (CRD-level) — no namespace; cluster-scoped object.
    crd_metadata: dict[str, Any] = {"name": gvk.crd_name}

    names: dict[str, Any] = {
        "kind": kind_value,
        "listKind": f"{kind_value}List",
        "plural": gvk.kind.plural,
        "singular": gvk.kind.singular,
        "shortNames": [],
    }

    version_entry: dict[str, Any] = {
        "name": gvk.version.value,
        "served": True,
        "storage": True,
        "schema": {"openAPIV3Schema": _sort_schema(structural)},
        "subresources": {"status": {}},
    }

    spec: dict[str, Any] = {
        "group": gvk.group.value,
        "names": names,
        "scope": _CRD_SCOPE,
        "versions": [version_entry],
    }

    return {
        "apiVersion": _CRD_API_VERSION,
        "kind": _CRD_KIND,
        "metadata": crd_metadata,
        "spec": spec,
    }


def _strip_injected_keys(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``schema`` with the API-server-injected keys gone.

    Always sets ``type: object`` at the root (Kubernetes structural
    schemas demand it). ``properties`` is filtered to drop the
    ``apiVersion`` / ``kind`` / ``metadata`` injectees. ``required`` is
    re-sorted defensively and any reference to a stripped key is
    removed.
    """
    out: dict[str, Any] = {"type": "object"}
    # Carry through every non-properties / non-required key verbatim
    # (including ``description`` and any ``x-kubernetes-*`` extensions).
    for k, v in schema.items():
        if k in {"type", "properties", "required"}:
            continue
        out[k] = v

    props = schema.get("properties")
    if isinstance(props, Mapping):
        filtered: dict[str, Any] = {
            name: value
            for name, value in props.items()
            if name not in _INJECTED_TOPLEVEL_KEYS
        }
        out["properties"] = filtered

    required = schema.get("required")
    if isinstance(required, list):
        # Drop any reference to stripped keys; sort the rest.
        out["required"] = sorted(
            r for r in required if r not in _INJECTED_TOPLEVEL_KEYS
        )

    return out


def _sort_schema(value: Any) -> Any:
    """Return a recursively key-sorted copy of ``value``.

    Mirrors ``OpenAPIDocument._sorted`` semantics: dicts are sorted by
    key, lists are walked element-wise, scalars pass through. Operating
    on the dict before YAML dumping is what makes the output
    byte-stable independent of the dict insertion order in upstream
    builders.
    """
    if isinstance(value, Mapping):
        return {k: _sort_schema(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_sort_schema(item) for item in value]
    return value


__all__ = ["CrdYamlGenerator"]
