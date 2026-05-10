"""RequestEnhancer domain service.

Applies safe defaults to a parsed :class:`CodegenRequest` so the rest
of the pipeline does not have to deal with sentinel values. See
``docs/ddd/bounded-contexts/01-intent-interpretation.md`` section 4.

The current responsibilities are:

1. Substitute a default ``output_path`` if the parsed request used the
   conventional sentinel
   (``OutputPath(root=<cwd>, relative=Path("__default__"))``).
   The default is ``OutputPath(root=cwd, relative="generated_specs/<kind_lower>")``.
2. Substitute a default ``description`` if the user did not supply one
   (i.e. the description is blank or matches the conventional
   ``"__default__"`` sentinel).

The service is **pure**: it never mutates its input — it returns a
fresh ``CodegenRequest`` via the aggregate's ``with_*`` builders.
"""

from __future__ import annotations

from pathlib import Path

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.values import OutputPath

#: Sentinel used by upstream parsers to signal "no description supplied".
_DEFAULT_DESCRIPTION_SENTINEL = "__default__"

#: Sentinel relative path used by upstream parsers to signal "fill in
#: the conventional default".
_DEFAULT_RELATIVE_SENTINEL = Path("__default__")


class RequestEnhancer:
    """Stateless service that fills in safe defaults on a request."""

    def __init__(self, *, default_root: Path | None = None) -> None:
        """Create an enhancer.

        Parameters
        ----------
        default_root:
            The filesystem root used to anchor a default ``output_path``.
            If ``None`` (the default), the current working directory is
            used at call time. Tests should pass an explicit root for
            determinism.
        """
        self._default_root = default_root

    def enhance(self, request: CodegenRequest) -> CodegenRequest:
        """Return ``request`` with sentinel fields replaced by defaults."""
        out = request

        if request.output_path.relative == _DEFAULT_RELATIVE_SENTINEL:
            root = (self._default_root or Path.cwd()).resolve()
            kind_lower = request.gvk.kind.value.lower()
            new_path = OutputPath(
                root=root,
                relative=Path("generated_specs") / kind_lower,
            )
            out = out.with_output_path(new_path)

        if request.description.strip() in {"", _DEFAULT_DESCRIPTION_SENTINEL}:
            kind_value = request.gvk.kind.value
            out = out.with_description(
                f"Auto-generated CRD for the {kind_value} API."
            )

        return out


__all__ = ["RequestEnhancer"]
