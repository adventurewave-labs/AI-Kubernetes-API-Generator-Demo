"""``SecretProvider`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 5.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """Resolve named secrets to their string value (or ``None``)."""

    def get(self, name: str) -> str | None:
        """Return the secret value or ``None`` if not present."""

    def names(self) -> list[str]:
        """Return the list of known secret names (for diagnostics)."""
