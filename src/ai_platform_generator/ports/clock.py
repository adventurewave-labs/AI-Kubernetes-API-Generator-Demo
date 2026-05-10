"""``Clock`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 7. The ``Clock``
port exists so that golden tests do not depend on wall time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provide the current time, abstracted for testability."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC ``datetime``."""

    def monotonic(self) -> float:
        """Return a monotonically increasing float (seconds, arbitrary epoch)."""
