"""Go controller artefact generator.

Emits a six-file kubebuilder-style scaffold under ``<target>/controller/``
per :doc:`../../../../../docs/adr/0011-go-controller-kubebuilder-scaffold`
and ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.2.3:

::

    <output>/controller/
    ├── main.go
    ├── api/<version>/<kindLower>_types.go
    ├── internal/controller/<kindLower>_controller.go
    ├── Dockerfile
    ├── go.mod
    └── Makefile

The generator is **byte-deterministic by construction**: templates are
rendered with ``StrictUndefined`` (no missing-variable fallthrough), the
``properties`` plan-metadata is built from a stably-sorted IR, and
``_post_process`` invokes ``gofmt`` (a deterministic formatter) when it
is present on ``$PATH``. When ``gofmt`` is missing or fails, the
unformatted bytes are kept and a warning is written to ``stderr`` —
formatting is a hygiene step, never a correctness gate.

Known limitations (out of scope for v1, called out in ADR-0011):

* Object spec properties (``PropertyType.OBJECT``) are mapped to
  ``map[string]string`` placeholders. Full nested-struct generation is
  post-v1.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile
from ai_platform_generator.domain.generation.renderer import Renderer
from ai_platform_generator.domain.services.checksum_service import ChecksumService

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

#: On-disk subdirectory under the bundle target that holds every Go
#: controller file.
CONTROLLER_SUBDIR = "controller"

#: Default ``controller-runtime`` release pinned in ``go.mod``. Track
#: latest LTS; bump in lockstep with ``KUBERNETES_API_VERSION_DEFAULT``.
CONTROLLER_RUNTIME_VERSION_DEFAULT = "v0.18.4"

#: Default ``k8s.io/{api,apimachinery,client-go}`` version.
KUBERNETES_API_VERSION_DEFAULT = "v0.30.3"

#: Default Go toolchain version stamped into ``go.mod`` and the
#: ``Dockerfile`` builder stage.
GO_VERSION_DEFAULT = "1.22"

#: Wall-clock cap on a single ``gofmt`` invocation. Generous because
#: gofmt is fast, but bounded so a stuck tool cannot wedge generation.
_GOFMT_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Type-mapping table
# ---------------------------------------------------------------------------
#
# Mapping from the IR's ``PropertyType`` (and array ``item_type``) to the
# Go type used in the generated ``<Kind>Spec`` struct. Single source of
# truth for ``test_go_controller_type_mapping.py`` so a regression in
# either direction breaks loud. ``OBJECT`` is a documented v1 limitation
# (see module docstring) — we emit ``map[string]string``.
_SCALAR_GO_TYPES: dict[str, str] = {
    "string": "string",
    "integer": "int32",
    "number": "float64",
    "boolean": "bool",
}


def _scalar_go_type(scalar: str) -> str:
    """Look up the Go type for a scalar JSON-Schema type name.

    Accepts the lowercase JSON-Schema spelling (``string``, ``integer``,
    ``number``, ``boolean``). Raises :class:`ArtifactGenerationError`
    for anything else — the generator should never see a non-scalar
    array item type because :class:`SpecProperty` already enforces that
    invariant, but we re-raise as a generation-stage error for callers
    that hit the helper directly.
    """
    try:
        return _SCALAR_GO_TYPES[scalar]
    except KeyError as exc:
        raise ArtifactGenerationError(
            f"GoControllerGenerator: unsupported scalar JSON-Schema type "
            f"{scalar!r} (expected one of {sorted(_SCALAR_GO_TYPES)!r})"
        ) from exc


def _go_type_for(
    type_: str, item_type: str | None = None, *, required: bool = True
) -> str:
    """Return the Go type for an IR property.

    Parameters
    ----------
    type_:
        JSON-Schema type name (``string``, ``integer``, ``number``,
        ``boolean``, ``array``, ``object``).
    item_type:
        Element type when ``type_ == "array"``; ignored otherwise.
    required:
        When ``False``, scalars are wrapped in a Go pointer so callers
        can detect the "unset" case (``*string``, ``*int32``, …).
        Composite types (``[]T``, ``map[...]...``) are not pointer-wrapped
        because their zero value already carries the unset signal
        (``nil``).
    """
    if type_ == "array":
        if item_type is None:
            raise ArtifactGenerationError(
                "GoControllerGenerator: array property is missing item_type"
            )
        return f"[]{_scalar_go_type(item_type)}"
    if type_ == "object":
        # Documented v1 limitation — see module docstring.
        return "map[string]string"
    base = _scalar_go_type(type_)
    return base if required else f"*{base}"


# ---------------------------------------------------------------------------
# Property-row dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PropertyRow:
    """One row of the ``<Kind>Spec`` struct, ready for the Jinja template."""

    name: str
    go_field: str
    go_type: str
    json_tag: str
    description: str
    required: bool


def _camel_to_pascal(name: str) -> str:
    """Convert a camelCase JSON name to PascalCase for a Go field.

    Empty strings are forbidden by :class:`SpecProperty`'s regex, so we
    only need to upper-case the first character.
    """
    if not name:
        return name
    return name[0].upper() + name[1:]


# ---------------------------------------------------------------------------
# Plan-metadata helpers
# ---------------------------------------------------------------------------


def _version_pkg(version_value: str) -> str:
    """Return the Go *package name* for an API version.

    Examples: ``v1`` → ``v1``; ``v1alpha1`` → ``v1alpha1``;
    a hypothetical ``v1.0`` → ``v10`` (dots stripped). Always
    lower-case.
    """
    return version_value.lower().replace(".", "")


def _build_property_rows(
    schemas: Mapping[str, Any], kind: str
) -> tuple[_PropertyRow, ...]:
    """Walk the IR's ``<Kind>.spec`` schema and return one row per property.

    The IR is built deterministically (keys sorted by
    :func:`OpenAPIDocument._sorted_dict`), so iterating ``properties``
    in dict order is already stable — but we sort defensively here too,
    so the templated output never depends on Python dict-iteration
    nuances.
    """
    kind_schema = schemas.get(kind)
    if kind_schema is None:
        # Defensive: should never happen because _check_preconditions has
        # already asserted the IR shape, but guard anyway.
        raise ArtifactGenerationError(  # pragma: no cover - defensive
            f"GoControllerGenerator: IR has no schema for kind {kind!r}"
        )
    spec_schema = kind_schema.get("properties", {}).get("spec", {})
    spec_props = spec_schema.get("properties", {}) or {}
    required: set[str] = set(spec_schema.get("required", []) or [])

    rows: list[_PropertyRow] = []
    for name in sorted(spec_props.keys()):
        prop_schema = spec_props[name] or {}
        json_type = prop_schema.get("type", "string")
        item_type: str | None = None
        if json_type == "array":
            items = prop_schema.get("items") or {}
            item_type = items.get("type")
        is_required = name in required
        go_type = _go_type_for(json_type, item_type, required=is_required)
        rows.append(
            _PropertyRow(
                name=name,
                go_field=_camel_to_pascal(name),
                go_type=go_type,
                json_tag=name if is_required else f"{name},omitempty",
                description=str(prop_schema.get("description", "")).strip()
                or f"Specification for {name}",
                required=is_required,
            )
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class GoControllerGenerator(ArtifactGenerator):
    """Emit the six-file kubebuilder Go controller scaffold."""

    name = "go_controller"
    artefact_type = ArtifactType.GO_CONTROLLER

    def __init__(
        self,
        *,
        go_module_name: str | None = None,
        controller_runtime_version: str = CONTROLLER_RUNTIME_VERSION_DEFAULT,
        kubernetes_api_version: str = KUBERNETES_API_VERSION_DEFAULT,
        go_version: str = GO_VERSION_DEFAULT,
        renderer: Renderer | None = None,
        checksum_service: ChecksumService | None = None,
    ) -> None:
        """Construct a Go controller generator.

        Parameters
        ----------
        go_module_name:
            Module path stamped into ``go.mod`` (e.g.
            ``github.com/acme/widget-operator``). When ``None``, a
            deterministic default is derived from the IR's
            ``Kind`` at plan time:
            ``github.com/example/<kindLower>-operator``.
        controller_runtime_version:
            Pinned ``sigs.k8s.io/controller-runtime`` release.
        kubernetes_api_version:
            Pinned ``k8s.io/{api,apimachinery,client-go}`` release.
        go_version:
            Go toolchain version stamped into ``go.mod`` and the
            Dockerfile builder stage.
        renderer:
            Optional pre-built :class:`Renderer`. When ``None``, a
            renderer pointed at ``src/ai_platform_generator/templates/go``
            is built lazily.
        checksum_service:
            Override for tests; otherwise a default
            :class:`ChecksumService` is constructed by the base class.
        """
        super().__init__(checksum_service=checksum_service)
        self._go_module_name_override = go_module_name
        self._controller_runtime_version = controller_runtime_version
        self._kubernetes_api_version = kubernetes_api_version
        self._go_version = go_version
        self._renderer = renderer or self._default_renderer()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_renderer() -> Renderer:
        """Build a :class:`Renderer` rooted at ``templates/go``.

        Walks up two parents from this file to reach the package root,
        then dives into ``templates/go``. Done at instance construction
        so the path lookup happens once per generator.
        """
        templates_root = (
            Path(__file__).resolve().parents[3] / "templates" / "go"
        )
        return Renderer(searchpath=templates_root)

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        """Validate the IR carries a GVK extension and a non-empty Spec."""
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"GoControllerGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        # Force-trigger the GVK extraction to surface "missing extension"
        # as an ArtifactGenerationError rather than InvalidOpenAPIDocument
        # (the IR has already passed earlier validation gates).
        try:
            _ = ir.gvk
        except Exception as exc:  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"GoControllerGenerator: IR has no GVK extension: {exc}"
            ) from exc

        kind = ir.gvk.kind.value
        kind_schema = ir.schemas.get(kind)
        if kind_schema is None:
            raise ArtifactGenerationError(
                f"GoControllerGenerator: IR has no schema for kind {kind!r}"
            )
        try:
            spec_schema = kind_schema.get("properties", {}).get("spec", {})
        except AttributeError:  # pragma: no cover - defensive
            spec_schema = {}
        spec_props = spec_schema.get("properties", {}) or {}
        if not spec_props:
            raise ArtifactGenerationError(
                f"GoControllerGenerator: spec for kind {kind!r} has no properties"
            )

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        gvk = ir.gvk
        kind = gvk.kind.value
        kind_lower = gvk.kind.value.lower()
        kind_plural = gvk.kind.plural
        version_pkg = _version_pkg(gvk.version.value)
        group = gvk.group.value
        module = (
            self._go_module_name_override
            or f"github.com/example/{kind_lower}-operator"
        )

        rows = _build_property_rows(ir.schemas, kind)
        # Tuple-of-dicts so the Jinja templates can use attribute-style
        # access and the metadata stays JSON-serialisable for tests.
        properties_payload: tuple[Mapping[str, Any], ...] = tuple(
            MappingProxyType(
                {
                    "name": row.name,
                    "go_field": row.go_field,
                    "go_type": row.go_type,
                    "json_tag": row.json_tag,
                    "description": row.description,
                    "required": row.required,
                }
            )
            for row in rows
        )

        ctrl_root = target / CONTROLLER_SUBDIR
        target_files: tuple[Path, ...] = (
            ctrl_root / "main.go",
            ctrl_root / "api" / version_pkg / f"{kind_lower}_types.go",
            ctrl_root / "internal" / "controller" / f"{kind_lower}_controller.go",
            ctrl_root / "Dockerfile",
            ctrl_root / "go.mod",
            ctrl_root / "Makefile",
        )

        metadata: dict[str, Any] = {
            "gvk": {
                "group": group,
                "version": gvk.version.value,
                "kind": kind,
            },
            "go_module_name": module,
            "controller_runtime_version": self._controller_runtime_version,
            "kubernetes_api_version": self._kubernetes_api_version,
            "go_version": self._go_version,
            "version_pkg": version_pkg,
            "kind": kind,
            "kind_lower": kind_lower,
            "kind_plural": kind_plural,
            "group": group,
            "properties": properties_payload,
        }

        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=target_files,
            metadata=metadata,
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        ctx: dict[str, Any] = {
            "kind": plan.metadata["kind"],
            "kind_lower": plan.metadata["kind_lower"],
            "kind_plural": plan.metadata["kind_plural"],
            "group": plan.metadata["group"],
            "version_pkg": plan.metadata["version_pkg"],
            "go_module_name": plan.metadata["go_module_name"],
            "go_version": plan.metadata["go_version"],
            "controller_runtime_version": plan.metadata[
                "controller_runtime_version"
            ],
            "kubernetes_api_version": plan.metadata["kubernetes_api_version"],
            "properties": plan.metadata["properties"],
        }

        # Files in the same order as ``plan.target_files`` so the index
        # alignment with ``_TEMPLATE_NAMES`` stays self-evident.
        template_names = (
            "main.go.j2",
            "types.go.j2",
            "controller.go.j2",
            "Dockerfile.j2",
            "go.mod.j2",
            "Makefile.j2",
        )

        if len(template_names) != len(plan.target_files):  # pragma: no cover
            raise ArtifactGenerationError(
                "GoControllerGenerator: template/target count mismatch"
            )

        rendered: list[_RenderedFile] = []
        for template_name, target_path in zip(
            template_names, plan.target_files, strict=True
        ):
            text = self._renderer.render(template_name, ctx)
            rendered.append(
                _RenderedFile(path=target_path, payload=text.encode("utf-8"))
            )
        return tuple(rendered)

    def _post_process(
        self, files: tuple[_RenderedFile, ...]
    ) -> tuple[_RenderedFile, ...]:
        """Run ``gofmt`` on every ``.go`` file when the binary is on PATH.

        On any failure (binary missing, non-zero exit, timeout) we keep
        the unformatted bytes and write a single warning to ``stderr``.
        ``gofmt`` is hygiene; it must never gate generation success.
        """
        gofmt_path = shutil.which("gofmt")
        if gofmt_path is None:
            self._warn(
                "gofmt not found on PATH — emitting unformatted Go sources",
            )
            return files

        out: list[_RenderedFile] = []
        for file in files:
            if file.path.suffix != ".go":
                out.append(file)
                continue
            formatted = self._gofmt(gofmt_path, file.payload, file.path)
            out.append(
                _RenderedFile(path=file.path, payload=formatted)
                if formatted is not None
                else file
            )
        return tuple(out)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _gofmt(
        self, gofmt_path: str, payload: bytes, path: Path
    ) -> bytes | None:
        """Run ``gofmt`` and return the formatted bytes or ``None`` on failure."""
        try:
            result = subprocess.run(
                [gofmt_path],
                input=payload,
                capture_output=True,
                timeout=_GOFMT_TIMEOUT_SECONDS,
                check=False,
                shell=False,
            )
        except FileNotFoundError:
            self._warn(
                f"gofmt vanished between PATH lookup and exec — "
                f"keeping unformatted bytes for {path.name}"
            )
            return None
        except subprocess.TimeoutExpired:
            self._warn(
                f"gofmt timed out after {_GOFMT_TIMEOUT_SECONDS}s — "
                f"keeping unformatted bytes for {path.name}"
            )
            return None

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            self._warn(
                f"gofmt failed on {path.name} (exit {result.returncode}): "
                f"{stderr or '<no stderr>'} — keeping unformatted bytes"
            )
            return None
        return result.stdout

    @staticmethod
    def _warn(message: str) -> None:
        """Emit a warning to stderr. No log dependency; never raises."""
        print(f"[go_controller] WARNING: {message}", file=sys.stderr)


__all__ = [
    "CONTROLLER_RUNTIME_VERSION_DEFAULT",
    "CONTROLLER_SUBDIR",
    "GO_VERSION_DEFAULT",
    "KUBERNETES_API_VERSION_DEFAULT",
    "GoControllerGenerator",
]
