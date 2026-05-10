"""Built-in artefact generators.

Each module in this package registers a concrete
:class:`ArtifactGenerator` subclass with the global generator registry
via the :func:`register_generator` decorator from
:mod:`ai_platform_generator.domain.generation.artifact_generator`.

The :func:`default_generators` factory returns the canonical default
set used by ``composition.py`` when wiring the ``GenerationOrchestrator``
in Wave 4.

Sibling agents land generators in parallel during Wave 4 (Agent M owns
``go_controller.py``). To keep this module loadable while the
go-controller code is in flight, that one generator is imported via a
defensive ``try/except ImportError`` block; everything else is a hard
import. :func:`unavailable_generators` exposes the per-name error
string so tests (notably the golden-file matrix) can skip cleanly with
a clear message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_platform_generator.domain.generation.artifact_generator import (
    ArtifactGenerator,
)
from ai_platform_generator.domain.generation.generators.crd import CrdYamlGenerator
from ai_platform_generator.domain.generation.generators.instance import (
    InstanceYamlGenerator,
)
from ai_platform_generator.domain.generation.generators.kustomization import (
    KustomizationGenerator,
)
from ai_platform_generator.domain.generation.generators.mcp_server import (
    McpServerGenerator,
)
from ai_platform_generator.domain.generation.generators.openapi import OpenApiGenerator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.generation.generators.go_controller import (
        GoControllerGenerator,
    )

_unavailable: dict[str, str] = {}

try:  # pragma: no cover - import-error branch is environment-specific
    from ai_platform_generator.domain.generation.generators.go_controller import (
        GoControllerGenerator,
    )
except ImportError as exc:  # pragma: no cover
    _unavailable["go_controller"] = str(exc)
    GoControllerGenerator = None  # type: ignore[assignment,misc]


def default_generators() -> tuple[ArtifactGenerator, ...]:
    """Return a fresh tuple of the registered generator instances.

    Returned in the on-disk order (OpenAPI → CRD → instance →
    Go controller → MCP server → kustomization) so the
    ``ArtifactPlanner`` sees a deterministic iteration order. The Go
    controller is included only when its module is importable (Wave-4
    parallel-agent reconciliation may briefly have it absent).
    """
    generators: list[ArtifactGenerator] = [
        OpenApiGenerator(),
        CrdYamlGenerator(),
        InstanceYamlGenerator(),
    ]
    if "go_controller" not in _unavailable and GoControllerGenerator is not None:
        generators.append(GoControllerGenerator())
    generators.append(McpServerGenerator())
    generators.append(KustomizationGenerator())
    return tuple(generators)


def unavailable_generators() -> dict[str, str]:
    """Return ``{generator-module-name: import-error}`` for missing modules.

    Empty when every generator module imported successfully. Tests use
    this to skip golden expectations for generators that aren't yet on
    disk; post-Wave-4 reconciliation gates on this dict being empty.
    """
    return dict(_unavailable)


__all__ = [
    "CrdYamlGenerator",
    "GoControllerGenerator",
    "InstanceYamlGenerator",
    "KustomizationGenerator",
    "McpServerGenerator",
    "OpenApiGenerator",
    "default_generators",
    "unavailable_generators",
]
