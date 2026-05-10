"""Kustomization (``kustomization.yaml``) artefact generator.

Emits a single Kustomize entrypoint at the bundle root that references
the CRD and instance YAMLs produced by sibling generators
(:class:`CrdYamlGenerator`, :class:`InstanceYamlGenerator`). The output
is byte-deterministic by construction:

* PyYAML is invoked with ``sort_keys=False, default_flow_style=False``
  so we control the emission order ourselves.
* ``resources`` is sorted lexicographically.
* ``commonLabels`` keys are sorted lexicographically (we build the
  mapping from a sorted list of pairs).

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.2.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile

#: Stable on-disk filename for the kustomization artefact.
KUSTOMIZATION_FILENAME = "kustomization.yaml"

#: API version emitted in the kustomization stanza.
_KUSTOMIZE_API_VERSION = "kustomize.config.k8s.io/v1beta1"

#: ``kind`` field of the kustomization stanza.
_KUSTOMIZE_KIND = "Kustomization"

#: Label value tagging artefacts as produced by this tool.
_MANAGED_BY = "ai-platform-generator"


@register_generator
class KustomizationGenerator(ArtifactGenerator):
    """Emit a ``kustomization.yaml`` at the bundle root.

    The kustomization references the CRD and instance YAML files using
    the *relative* paths sibling generators write — i.e.
    ``<kindLower>.crd.yaml`` and ``<kindLower>.instance.yaml`` — under
    the assumption all three files are co-located at the bundle root.

    Output is a single, byte-stable YAML document.
    """

    name = "kustomization"
    artefact_type = ArtifactType.KUSTOMIZATION

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        """Reject IRs lacking the GVK ``info.x-kubernetes-gvk`` extension."""
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"KustomizationGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        # ``OpenAPIDocument.gvk`` raises InvalidOpenAPIDocument if the
        # extension is missing/malformed — convert to ArtifactGenerationError
        # so callers see a generation-stage failure rather than an IR
        # invariant violation (the IR has already been built and is
        # accepted by other generators).
        try:
            _ = ir.gvk
        except Exception as exc:  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"KustomizationGenerator: IR has no GVK extension: {exc}"
            ) from exc

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / KUSTOMIZATION_FILENAME,),
            metadata={"kind": ir.gvk.kind.value, "kind_lower": ir.gvk.kind.value.lower()},
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        kind_lower = plan.metadata["kind_lower"]
        assert isinstance(kind_lower, str)

        resources = sorted(
            [
                f"{kind_lower}.crd.yaml",
                f"{kind_lower}.instance.yaml",
            ]
        )
        labels: dict[str, str] = {
            k: v
            for k, v in sorted(
                {
                    "app.kubernetes.io/managed-by": _MANAGED_BY,
                    "app.kubernetes.io/name": kind_lower,
                }.items()
            )
        }

        # Build the document with explicit key ordering to guarantee
        # byte-stable output regardless of dict insertion-order quirks.
        doc: dict[str, object] = {
            "apiVersion": _KUSTOMIZE_API_VERSION,
            "kind": _KUSTOMIZE_KIND,
            "resources": resources,
            "commonLabels": labels,
        }

        text = yaml.safe_dump(
            doc,
            default_flow_style=False,
            sort_keys=False,
        )
        payload = text.encode("utf-8")
        return (_RenderedFile(path=plan.target_files[0], payload=payload),)


__all__ = ["KUSTOMIZATION_FILENAME", "KustomizationGenerator"]
