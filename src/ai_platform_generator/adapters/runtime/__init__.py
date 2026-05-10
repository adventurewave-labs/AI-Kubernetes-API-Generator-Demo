"""Runtime adapters (Kubernetes, processes)."""

from __future__ import annotations

from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime

__version__ = "0.1.0"

__all__ = ["FakeClusterRuntime", "__version__"]
