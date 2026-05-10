"""Version value object.

A Kubernetes API *version* string, e.g. ``v1``, ``v1alpha1``, ``v2beta3``.

See ``docs/ddd/04-tactical-design.md`` section 2.2 for the contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ai_platform_generator.domain.errors import InvalidVersion

_VERSION_RE = re.compile(r"^v\d+(?:(?:alpha|beta)\d+)?$")

Stability = Literal["alpha", "beta", "ga"]


@dataclass(frozen=True, slots=True)
class Version:
    """An immutable, validated Kubernetes API version string."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _VERSION_RE.fullmatch(self.value):
            raise InvalidVersion(self.value)

    @property
    def stability(self) -> Stability:
        if "alpha" in self.value:
            return "alpha"
        if "beta" in self.value:
            return "beta"
        return "ga"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
