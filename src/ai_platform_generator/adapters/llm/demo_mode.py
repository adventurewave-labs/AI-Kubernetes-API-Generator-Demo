"""Deterministic in-process LLM adapter — the demo-mode fallback.

Implements :class:`LlmProvider` per :doc:`../../../docs/adr/0009-graceful-degradation-to-demo-mode`.
The adapter has no network dependencies, is *always* available, and
returns a curated JSON payload chosen by keyword-matching the user
prompt against a :class:`DemoCatalog`.

Response shape contract
-----------------------
The :class:`LlmProvider` contract (encoded in
``prompts/v1/intent_interpretation.txt``) requires the legacy
"intent prompt" shape consumed by
:meth:`IntentInterpretationService._build_request`:

* ``group`` (string, top-level)
* ``version`` (string, top-level)
* ``kind`` (string, top-level)
* ``spec_properties`` — object keyed by camelCase property name; each
  value is an object with at least a ``type`` field plus optional
  ``description`` / ``item_type`` / constraint fields (inlined, not
  nested under ``constraints``).
* ``output_dir`` (string, relative path)
* ``description`` (string)

The :class:`DemoCatalog`, however, persists the *modern*
``CodegenRequest.to_dict()`` shape (nested ``gvk``, ``spec_properties``
as an ordered list, ``output_path`` with ``root`` + ``relative``). The
catalogue shape is what golden tests round-trip through
:meth:`CodegenRequest.from_dict`. This adapter translates the catalogue
shape into the legacy intent shape on every call so the
:class:`IntentInterpretationService` parser is satisfied — that is the
bug Wave 8 chunk (1) fixes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.values import ProviderMode


class DemoModeLlmAdapter:
    """An always-available, deterministic ``LlmProvider`` fallback.

    Construction is cheap; no I/O is performed at any point. Each call
    to :meth:`complete_json` selects a :class:`DemoScenario` from the
    catalogue using keyword-matching on the ``user_prompt`` and returns
    the scenario's curated payload translated into the legacy intent
    shape expected by :class:`IntentInterpretationService`.
    """

    name: str = "demo"
    model: str = "demo-catalog-v1"

    def __init__(self, catalog: DemoCatalog | None = None) -> None:
        self._catalog: DemoCatalog = catalog if catalog is not None else DemoCatalog()
        self.mode: ProviderMode = ProviderMode.DEMO
        # Test/diagnostic surface: which scenario was last served.
        self._last_scenario_name: str | None = None

    @property
    def catalog(self) -> DemoCatalog:
        """The catalogue this adapter is reading from."""
        return self._catalog

    @property
    def last_scenario_name(self) -> str | None:
        """Name of the scenario served by the most recent call."""
        return self._last_scenario_name

    def is_available(self) -> bool:
        """Demo mode never fails; always returns ``True``."""
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        """Return the LLM-intent JSON payload for the matching demo scenario.

        Falls back to the catalogue's default scenario (``vector-db`` by
        default) when no keyword matches the ``user_prompt``. The
        returned dict is shaped per the :class:`LlmProvider` contract,
        not :meth:`CodegenRequest.to_dict`.
        """
        scenario = self._catalog.find(user_prompt)
        self._last_scenario_name = scenario.name
        # Translate the catalogue's ``to_dict``-shaped payload into the
        # legacy intent shape. Defensive copies prevent mutation leaking
        # back into the catalogue.
        return _scenario_request_to_intent_shape(scenario.request)


def _scenario_request_to_intent_shape(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert a catalogue payload (modern `CodegenRequest.to_dict` shape) to legacy intent shape.

    The translation is total — every catalogue scenario produces a
    response that satisfies
    :meth:`IntentInterpretationService._build_request`. If the input is
    *already* in the legacy shape (top-level ``group``/``version``/
    ``kind``) we return a defensive copy so custom catalogues authored
    against the older contract continue to work.
    """
    # If the payload already looks legacy-shaped, just hand back a copy.
    if "group" in request and "version" in request and "kind" in request:
        return dict(request)

    gvk = request.get("gvk")
    if isinstance(gvk, Mapping):
        group = str(gvk.get("group", "platform.cnoe.io"))
        version = str(gvk.get("version", "v1alpha1"))
        kind = str(gvk.get("kind", "GenericService"))
    else:
        # Defensive: a catalogue without GVK at all should still produce
        # a valid response so the orchestrator does not crash.
        group = "platform.cnoe.io"
        version = "v1alpha1"
        kind = "GenericService"

    # ``spec_properties`` is a list of objects in the modern shape; the
    # legacy intent shape wants a name → descriptor mapping. Inline any
    # constraint fields the parser understands.
    spec_props_legacy: dict[str, dict[str, Any]] = {}
    for prop in request.get("spec_properties") or ():
        if not isinstance(prop, Mapping):
            continue
        name = str(prop.get("name") or "")
        if not name:
            continue
        descriptor: dict[str, Any] = {
            "type": str(prop.get("type", "string")),
        }
        description = prop.get("description")
        if description:
            descriptor["description"] = str(description)
        item_type = prop.get("item_type")
        if item_type is not None:
            descriptor["item_type"] = str(item_type)
        constraints = prop.get("constraints")
        if isinstance(constraints, Mapping):
            for key in (
                "minimum",
                "maximum",
                "min_length",
                "max_length",
                "pattern",
                "format",
            ):
                value = constraints.get(key)
                if value is not None:
                    descriptor[key] = value
            enum = constraints.get("enum")
            if enum is not None:
                # Constraints store enum as a tuple; the parser expects a
                # list (or tuple) — normalise to list for JSON-friendly
                # output.
                descriptor["enum"] = list(enum)
        spec_props_legacy[name] = descriptor

    # ``output_dir`` lives at ``output_path.relative`` in the modern
    # shape; fall back to a deterministic per-kind default if absent.
    output_dir: str
    output_path = request.get("output_path")
    if isinstance(output_path, Mapping) and output_path.get("relative"):
        output_dir = str(output_path["relative"])
    else:
        output_dir = f"generated_specs/{kind.lower()}"

    description = str(
        request.get("description") or f"Auto-generated description for {kind}."
    )

    return {
        "group": group,
        "version": version,
        "kind": kind,
        "spec_properties": spec_props_legacy,
        "output_dir": output_dir,
        "description": description,
    }


__all__ = ["DemoModeLlmAdapter"]
