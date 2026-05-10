"""Clock adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.clock.system import SystemClock

__version__ = "0.1.0"

__all__ = ["FrozenClock", "SystemClock", "__version__"]
