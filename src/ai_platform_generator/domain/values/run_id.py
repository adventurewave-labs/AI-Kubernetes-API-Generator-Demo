"""RunId value object.

A globally-unique identifier for a single :class:`GenerationRun`. The
*intent* (per ``docs/ddd/04-tactical-design.md`` section 2.11) is a
UUIDv7 — time-ordered so that on-disk run logs sort lexicographically.

Implementation note
-------------------
Python's stdlib :mod:`uuid` does not yet ship a ``uuid7`` constructor
(as of 3.12). We therefore accept *any* RFC 4122 UUID string for now
and fall back to :func:`uuid.uuid4` in :meth:`RunId.new`. When a
UUIDv7 generator becomes part of the stdlib (or a vetted third-party
dependency is added) this module is the single point of change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ai_platform_generator.domain.errors import InvalidRunId


@dataclass(frozen=True, slots=True)
class RunId:
    """An immutable, validated run identifier.

    Parameters
    ----------
    value:
        The string form of a UUID. Any valid RFC 4122 representation
        is accepted (any version); the *intent* is UUIDv7 once stdlib
        support lands.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidRunId(f"value must be a str, got {type(self.value)!r}")
        try:
            parsed = uuid.UUID(self.value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise InvalidRunId(f"value {self.value!r} is not a valid UUID") from exc
        # Normalise: store the canonical lowercase, hyphenated form so
        # equality is stable regardless of input casing/braces.
        if str(parsed) != self.value:
            object.__setattr__(self, "value", str(parsed))

    @classmethod
    def new(cls) -> RunId:
        """Mint a fresh ``RunId``.

        Currently uses :func:`uuid.uuid4`. The *intent* is UUIDv7 so
        IDs sort by creation time; we accept the deviation while the
        stdlib catches up. Replace the body of this method when a
        UUIDv7 generator is available.
        """
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
