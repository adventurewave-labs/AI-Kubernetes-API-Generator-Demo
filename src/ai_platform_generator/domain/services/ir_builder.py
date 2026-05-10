"""IRBuilder domain service.

A thin, dependency-injectable wrapper around
:meth:`OpenAPIDocument.from_request`. The factory method is the
canonical builder; this service exists so the orchestrator can swap
implementations in tests (e.g. an instrumented builder that records
how many properties it has seen).

See ``docs/ddd/bounded-contexts/02-api-modelling.md`` section 4.
"""

from __future__ import annotations

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import OpenAPIDocument


class IRBuilder:
    """Pure ``CodegenRequest -> OpenAPIDocument`` builder."""

    def build(self, request: CodegenRequest) -> OpenAPIDocument:
        """Return the OpenAPI IR for ``request``.

        Determinism is enforced by the underlying factory: identical
        inputs produce byte-identical IR (see
        :meth:`OpenAPIDocument.serialise`).
        """
        return OpenAPIDocument.from_request(request)


__all__ = ["IRBuilder"]
