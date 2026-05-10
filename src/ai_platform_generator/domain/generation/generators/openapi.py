"""OpenAPI artefact generator.

Trivial generator that serialises the IR (an :class:`OpenAPIDocument`)
to a single ``openapi.json`` file under the target directory. The
implementation is deliberately the simplest possible — it exists partly
to validate the Template Method scaffolding (Wave 2) end-to-end before
the more involved CRD / instance / Go-controller generators land.

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.2 for the
contract.
"""

from __future__ import annotations

from pathlib import Path

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile

#: Stable on-disk filename for the OpenAPI artefact.
OPENAPI_FILENAME = "openapi.json"

#: Plan metadata key under which the IR-serialised bytes are stashed.
#: The ``_render`` step reads the bytes back so it can be a pure
#: function of the plan (no hidden ``self.ir`` state).
_PAYLOAD_KEY = "payload"


@register_generator
class OpenApiGenerator(ArtifactGenerator):
    """Serialise the IR to ``openapi.json``.

    The serialisation path is :meth:`OpenAPIDocument.serialise` (UTF-8
    JSON, sorted keys, trailing newline) — i.e. the *only* place IR
    bytes are produced — so this generator is byte-deterministic by
    construction.
    """

    name = "openapi"
    artefact_type = ArtifactType.OPENAPI

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        """Refuse to render if the IR has no schemas."""
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"OpenApiGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        if not ir.schemas:
            raise ArtifactGenerationError(
                "OpenApiGenerator: IR has no schemas — refusing to emit "
                "an empty OpenAPI document"
            )

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        # Serialise once here and stash the bytes in plan.metadata so
        # ``_render`` is a pure function of the plan — no IR reference
        # held on ``self``. The IR is already an immutable aggregate so
        # the bytes are stable across re-runs.
        payload = ir.serialise(indent=2)
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=(target / OPENAPI_FILENAME,),
            metadata={
                "kind": ir.gvk.kind.value,
                _PAYLOAD_KEY: payload,
            },
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        payload = plan.metadata[_PAYLOAD_KEY]
        if not isinstance(payload, bytes):  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"OpenApiGenerator: plan metadata['{_PAYLOAD_KEY}'] must be "
                f"bytes, got {type(payload).__name__}"
            )
        target_file = plan.target_files[0]
        return (_RenderedFile(path=target_file, payload=payload),)
