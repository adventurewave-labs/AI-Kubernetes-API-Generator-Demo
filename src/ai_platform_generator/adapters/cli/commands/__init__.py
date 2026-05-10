"""Click command groups exposed by ``adapters.cli.main``.

Each module owns one Click command (or group). They're bound onto the
top-level ``main`` group in :mod:`ai_platform_generator.adapters.cli.main`.
This package keeps no shared state — every command receives the
common config + renderer via Click's ``ctx.obj`` dict.
"""

from __future__ import annotations

from .build import build
from .cluster import cluster
from .examples import examples
from .generate import generate
from .interactive import interactive
from .runs import runs
from .validate import validate

__all__ = [
    "build",
    "cluster",
    "examples",
    "generate",
    "interactive",
    "runs",
    "validate",
]
