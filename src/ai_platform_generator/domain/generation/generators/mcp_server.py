"""MCP-server scaffold artefact generator.

Emits a *minimal but real* `Model Context Protocol`_ server scaffold
under ``mcp/`` at the bundle root. Output is a stub — it is meant to be
something a developer can pick up, ``pip install -r requirements.txt``,
and start filling in. It is **not** a working server out of the box;
the README is explicit about that.

The scaffold consists of three files:

* ``mcp/server.py`` — a FastMCP-style Python module declaring one
  ``@mcp.tool()`` per spec property of the IR.
* ``mcp/requirements.txt`` — pins ``mcp>=0.9`` and ``pydantic>=2.5``.
* ``mcp/README.md`` — short how-to-run-this-server document.

All three files are fully byte-deterministic given the same IR — the
generator does no time, randomness, or environment lookups. Tool order
follows the IR's declared spec-property order, which is itself stable
(the ``CodegenRequest.spec_properties`` tuple preserves its insertion
order). The README references the GVK so two scaffolds for different
kinds are textually distinguishable.

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §6.2 for the
contract.

.. _Model Context Protocol: https://modelcontextprotocol.io/
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ai_platform_generator.domain.aggregates import ArtifactType, OpenAPIDocument
from ai_platform_generator.domain.errors import ArtifactGenerationError
from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
    register_generator,
)
from ai_platform_generator.domain.generation.generation_plan import GenerationPlan
from ai_platform_generator.domain.generation.rendered_file import _RenderedFile

#: Bundle-relative directory under which all MCP-scaffold files live.
MCP_DIRNAME = "mcp"

#: Stable filenames inside ``mcp/`` — exposed for tests/golden infra.
MCP_SERVER_FILENAME = "server.py"
MCP_REQUIREMENTS_FILENAME = "requirements.txt"
MCP_README_FILENAME = "README.md"

#: Pinned dependency versions emitted in ``requirements.txt``.
_MCP_DEP = "mcp>=0.9"
_PYDANTIC_DEP = "pydantic>=2.5"


@register_generator
class McpServerGenerator(ArtifactGenerator):
    """Emit a FastMCP-style scaffold under ``mcp/``.

    The scaffold compiles (it is valid Python 3.10+) but the tool
    bodies are placeholders that ``raise NotImplementedError``. The
    README clearly marks the output as a starting point.
    """

    name = "mcp_server"
    artefact_type = ArtifactType.MCP_SERVER

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _check_preconditions(self, ir: OpenAPIDocument) -> None:
        """Reject non-OpenAPIDocument IRs and IRs lacking a GVK."""
        if not isinstance(ir, OpenAPIDocument):
            raise ArtifactGenerationError(
                f"McpServerGenerator requires an OpenAPIDocument, got {type(ir)!r}"
            )
        try:
            _ = ir.gvk
        except Exception as exc:  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                f"McpServerGenerator: IR has no GVK extension: {exc}"
            ) from exc

    def _plan(self, ir: OpenAPIDocument, target: Path) -> GenerationPlan:
        gvk = ir.gvk
        kind_lower = gvk.kind.value.lower()
        properties = _extract_spec_property_names(ir)

        mcp_dir = target / MCP_DIRNAME
        target_files = (
            mcp_dir / MCP_SERVER_FILENAME,
            mcp_dir / MCP_REQUIREMENTS_FILENAME,
            mcp_dir / MCP_README_FILENAME,
        )
        return GenerationPlan(
            generator_name=self.name,
            artefact_type=self.artefact_type,
            target_files=target_files,
            metadata={
                "group": gvk.group.value,
                "version": gvk.version.value,
                "kind": gvk.kind.value,
                "kind_lower": kind_lower,
                "description": ir.info.description,
                "properties": properties,
            },
        )

    def _render(self, plan: GenerationPlan) -> tuple[_RenderedFile, ...]:
        meta = plan.metadata
        group = _expect_str(meta, "group")
        version = _expect_str(meta, "version")
        kind = _expect_str(meta, "kind")
        kind_lower = _expect_str(meta, "kind_lower")
        description = _expect_str(meta, "description")
        properties_obj = meta.get("properties")
        if not isinstance(properties_obj, tuple):  # pragma: no cover - defensive
            raise ArtifactGenerationError(
                "McpServerGenerator: plan metadata['properties'] must be tuple, "
                f"got {type(properties_obj).__name__}"
            )
        properties: tuple[str, ...] = properties_obj

        server_path, requirements_path, readme_path = plan.target_files

        server_bytes = _render_server_py(
            group=group,
            version=version,
            kind=kind,
            kind_lower=kind_lower,
            description=description,
            properties=properties,
        ).encode("utf-8")
        requirements_bytes = _render_requirements_txt().encode("utf-8")
        readme_bytes = _render_readme_md(
            group=group,
            version=version,
            kind=kind,
            kind_lower=kind_lower,
            description=description,
            properties=properties,
        ).encode("utf-8")

        return (
            _RenderedFile(path=server_path, payload=server_bytes),
            _RenderedFile(path=requirements_path, payload=requirements_bytes),
            _RenderedFile(path=readme_path, payload=readme_bytes),
        )


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _expect_str(meta: Mapping[str, Any], key: str) -> str:
    val = meta.get(key)
    if not isinstance(val, str):  # pragma: no cover - defensive
        raise ArtifactGenerationError(
            f"McpServerGenerator: plan metadata[{key!r}] must be str, "
            f"got {type(val).__name__}"
        )
    return val


def _extract_spec_property_names(ir: OpenAPIDocument) -> tuple[str, ...]:
    """Return the (insertion-order) spec property names of the IR.

    The IR carries the spec under ``components.schemas.<Kind>.properties.spec.properties``.
    We pull names from there directly so the MCP scaffold stays in lock-step with
    whatever the IR actually shipped — no relying on a separately-stashed copy of
    the request.
    """
    kind = ir.gvk.kind.value
    schemas = dict(ir.schemas)
    kind_schema = schemas.get(kind)
    if not isinstance(kind_schema, Mapping):
        return ()
    properties = kind_schema.get("properties")
    if not isinstance(properties, Mapping):
        return ()
    spec = properties.get("spec")
    if not isinstance(spec, Mapping):
        return ()
    spec_props = spec.get("properties")
    if not isinstance(spec_props, Mapping):
        return ()
    # ``OpenAPIDocument.from_request`` lex-sorts the spec property dict for
    # determinism; re-sorting here is therefore a no-op but makes the rule
    # explicit if a future IR builder changes ordering.
    return tuple(sorted(spec_props.keys()))


def _render_server_py(
    *,
    group: str,
    version: str,
    kind: str,
    kind_lower: str,
    description: str,
    properties: tuple[str, ...],
) -> str:
    """Return the textual content of ``mcp/server.py``."""
    description_clean = " ".join(description.split()) or f"{kind} resource."
    server_name = f"{kind_lower}-mcp-server"

    lines: list[str] = []
    lines.append(f'"""MCP server scaffold for {kind} ({group}/{version}).')
    lines.append("")
    lines.append(f"Intent: {description_clean}")
    lines.append("")
    lines.append("This file is generated by ai-platform-generator. It is a *scaffold*:")
    lines.append("the tool bodies raise NotImplementedError until you fill them in.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from mcp.server.fastmcp import FastMCP")
    lines.append("")
    lines.append(f'mcp = FastMCP({server_name!r})')
    lines.append("")
    if not properties:
        lines.append("# No spec properties were declared on the source CRD; this scaffold")
        lines.append("# defines no tools. Add @mcp.tool() functions here as you grow the API.")
        lines.append("")
    else:
        for prop in properties:
            lines.append("@mcp.tool()")
            lines.append(f"def get_{prop}(name: str) -> dict:")
            lines.append(
                f'    """Return the current value of the ``{prop}`` field of a {kind}."""'
            )
            lines.append(
                f'    raise NotImplementedError("get_{prop} is a scaffold; implement me")'
            )
            lines.append("")
    lines.append("def main() -> None:")
    lines.append('    """Entry point — runs the MCP server until interrupted."""')
    lines.append("    mcp.run()")
    lines.append("")
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    main()")
    # Trailing newline.
    return "\n".join(lines) + "\n"


def _render_requirements_txt() -> str:
    """Return the textual content of ``mcp/requirements.txt``.

    Pinned, sorted, with a trailing newline.
    """
    deps = sorted([_MCP_DEP, _PYDANTIC_DEP])
    return "\n".join(deps) + "\n"


def _render_readme_md(
    *,
    group: str,
    version: str,
    kind: str,
    kind_lower: str,
    description: str,
    properties: tuple[str, ...],
) -> str:
    """Return the textual content of ``mcp/README.md``.

    A short how-to-run-this document. Roughly thirty lines, deterministic,
    explicitly references the GVK and the scaffold status.
    """
    description_clean = " ".join(description.split()) or f"{kind} resource."
    if properties:
        prop_list = "\n".join(f"- `get_{prop}`" for prop in properties)
    else:
        prop_list = "- _(no tools — the source CRD has no spec properties)_"

    template = (
        "# {kind} MCP Server (scaffold)\n"
        "\n"
        "**This is a scaffold, not a working server.** It was generated\n"
        "by `ai-platform-generator` and is intended as a starting point.\n"
        "Tool implementations raise `NotImplementedError` until you fill\n"
        "them in.\n"
        "\n"
        "## Source CRD\n"
        "\n"
        "- **Group:** `{group}`\n"
        "- **Version:** `{version}`\n"
        "- **Kind:** `{kind}`\n"
        "- **Intent:** {description_clean}\n"
        "\n"
        "## Tools exposed\n"
        "\n"
        "{prop_list}\n"
        "\n"
        "## Running\n"
        "\n"
        "```bash\n"
        "python -m venv .venv && source .venv/bin/activate\n"
        "pip install -r requirements.txt\n"
        "python server.py\n"
        "```\n"
        "\n"
        "The server speaks MCP over stdio by default.\n"
        "\n"
        "## Next steps\n"
        "\n"
        "1. Replace each tool body with real logic against your\n"
        "   `{kind_lower}` controller / API.\n"
        "2. Add authentication / authorisation as appropriate.\n"
        "3. Wire the server into your MCP client of choice.\n"
    )
    return template.format(
        kind=kind,
        group=group,
        version=version,
        description_clean=description_clean,
        prop_list=prop_list,
        kind_lower=kind_lower,
    )


__all__ = [
    "MCP_DIRNAME",
    "MCP_README_FILENAME",
    "MCP_REQUIREMENTS_FILENAME",
    "MCP_SERVER_FILENAME",
    "McpServerGenerator",
]
