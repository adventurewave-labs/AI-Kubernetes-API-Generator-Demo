"""``ApiModellingService`` — application service for the API Modelling context.

Per ``docs/ddd/06-application-services.md`` §6.2 the service is:

* pure (no IO);
* delegates IR construction to ``IRBuilder`` (Agent E);
* validates the produced IR via ``StructuralSchemaValidator`` (Agent E);
* emits ``IRConstructed`` / ``IRRejected`` events.

While Agent E's domain services have not yet landed, this service falls
back to ``OpenAPIDocument.from_request`` (already shipped with Wave 1
aggregates by Agent E) and skips structural validation. The fallback is
clearly marked so a quick-grep finds it once the dependency lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.errors import (
    DomainValidationError,
    UnsupportedSchema,
)
from ai_platform_generator.domain.events import IRConstructed, IRRejected

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        CodegenRequest,
        OpenAPIDocument,
    )
    from ai_platform_generator.domain.values import RunId
    from ai_platform_generator.ports import TelemetrySink


class ApiModellingService:
    """Build a validated :class:`OpenAPIDocument` from a ``CodegenRequest``."""

    def __init__(
        self,
        events: TelemetrySink,
        ir_builder: Any = None,  # domain.services.IRBuilder (Agent E)
        validator: Any = None,  # domain.services.StructuralSchemaValidator
    ) -> None:
        self._events = events
        self._ir_builder = ir_builder
        self._validator = validator

    def build(
        self, request: CodegenRequest, *, run_id: RunId | None = None
    ) -> OpenAPIDocument:
        """Construct the IR and validate it.

        Raises
        ------
        UnsupportedSchema
            If the structural-schema validator returns any violations.
        """
        # IRBuilder delegate: when Agent E's service is wired, prefer it.
        # Otherwise fall back to the aggregate's built-in factory so this
        # method remains operational during Wave 2.
        if self._ir_builder is not None:
            built: OpenAPIDocument = self._ir_builder.build(request)
            ir = built
        else:
            from ai_platform_generator.domain.aggregates.openapi_document import (
                OpenAPIDocument as _OpenAPIDocument,
            )

            ir = _OpenAPIDocument.from_request(request)

        # Structural validation: same Agent-E delegation pattern.
        violations = []
        if self._validator is not None:
            violations = list(self._validator.validate(ir) or [])

        if violations:
            self._events.emit(
                IRRejected.make(
                    run_id=run_id,
                    payload={
                        "violations": [
                            {
                                "path": v.path,
                                "expected": v.expected,
                                "actual": v.actual,
                                "message": v.message,
                            }
                            for v in violations
                        ]
                    },
                )
            )
            raise UnsupportedSchema(
                "structural validation",
                field_violations=list(violations),
            )

        try:
            gvk = ir.gvk
            gvk_payload = {
                "group": gvk.group.value,
                "version": gvk.version.value,
                "kind": gvk.kind.value,
            }
        except DomainValidationError:
            gvk_payload = {}

        self._events.emit(
            IRConstructed.make(
                run_id=run_id,
                payload={
                    "schema_count": len(ir.schemas),
                    "extension_count": len(ir.extensions),
                    "gvk": gvk_payload,
                },
            )
        )
        return ir
