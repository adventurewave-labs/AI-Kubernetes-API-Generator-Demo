"""Group value object.

A Kubernetes API *group* (reverse-DNS), e.g. ``platform.example.com``.

See ``docs/ddd/04-tactical-design.md`` section 2.1 for the contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_platform_generator.domain.errors import InvalidGroup

_GROUP_RE = re.compile(r"^[a-z0-9.-]+\.[a-z0-9.-]+$")


@dataclass(frozen=True, slots=True)
class Group:
    """An immutable, validated Kubernetes API group string.

    Invariants
    ----------
    - Lowercase only; digits, dots and hyphens permitted.
    - Must contain at least one dot (reverse-DNS shape).
    - No leading or trailing dot, no double dots.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _GROUP_RE.fullmatch(self.value):
            raise InvalidGroup(self.value)
        # Reject double-dots and leading/trailing dots explicitly so the
        # regex character-class does not accidentally accept e.g. "a..b".
        if ".." in self.value or self.value.startswith(".") or self.value.endswith("."):
            raise InvalidGroup(self.value)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
