"""Wall-clock :class:`Clock` adapter.

See ``docs/ddd/07-anti-corruption-layers.md`` section 7.2.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


class SystemClock:
    """Real wall-clock and ``time.monotonic`` clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()
