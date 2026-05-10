"""Kind value object.

A Kubernetes resource *kind*, PascalCase, e.g. ``Database``.

See ``docs/ddd/04-tactical-design.md`` section 2.3 for the contract,
including the English pluralisation rules used for CRD ``plural`` names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_platform_generator.domain.errors import InvalidKind

_KIND_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


@dataclass(frozen=True, slots=True)
class Kind:
    """An immutable, validated Kubernetes resource kind."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _KIND_RE.fullmatch(self.value):
            raise InvalidKind(self.value)

    @property
    def singular(self) -> str:
        """The kind name, lower-cased."""
        return self.value.lower()

    @property
    def plural(self) -> str:
        """English-language pluralisation, good enough for CRDs.

        Rules (per ``docs/ddd/04-tactical-design.md`` section 2.3):

        * Ends in ``s``  -> append ``es``  (e.g. ``Bus`` -> ``buses``).
        * Ends in ``y``  -> replace with ``ies`` (e.g. ``Policy`` -> ``policies``).
        * Otherwise      -> append ``s``  (e.g. ``Database`` -> ``databases``).
        """
        v = self.value.lower()
        if v.endswith("s"):
            return v + "es"
        if v.endswith("y"):
            return v[:-1] + "ies"
        return v + "s"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
