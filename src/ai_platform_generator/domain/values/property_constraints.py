"""PropertyConstraints value object.

Optional JSON-Schema-style constraints attached to a ``SpecProperty``.

See ``docs/ddd/04-tactical-design.md`` section 2.7 for the contract.

Note
----
``min_length`` / ``max_length`` are only semantically valid for
string-shaped types; enforcing the *combination* (PropertyType x
constraints) is the **caller's** responsibility (typically
``SpecProperty`` or the ``RequestValidator`` domain service). This
class only checks that the constraint *values themselves* are
internally consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_platform_generator.domain.errors import InvalidPropertyConstraints


@dataclass(frozen=True, slots=True)
class PropertyConstraints:
    """An immutable set of optional value constraints.

    All fields default to ``None`` (no constraint).

    Invariants
    ----------
    1. If both ``minimum`` and ``maximum`` are set, ``minimum <= maximum``.
    2. If both ``min_length`` and ``max_length`` are set,
       ``min_length <= max_length``.
    3. ``min_length`` and ``max_length`` must be non-negative.
    4. ``enum``, when set, must be non-empty.
    """

    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    enum: tuple[str, ...] | None = None
    format: str | None = None

    def __post_init__(self) -> None:
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise InvalidPropertyConstraints(
                f"minimum ({self.minimum}) must be <= maximum ({self.maximum})"
            )
        if self.min_length is not None and self.min_length < 0:
            raise InvalidPropertyConstraints(
                f"min_length must be non-negative, got {self.min_length}"
            )
        if self.max_length is not None and self.max_length < 0:
            raise InvalidPropertyConstraints(
                f"max_length must be non-negative, got {self.max_length}"
            )
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise InvalidPropertyConstraints(
                f"min_length ({self.min_length}) must be <= max_length ({self.max_length})"
            )
        if self.enum is not None and len(self.enum) == 0:
            raise InvalidPropertyConstraints("enum, when set, must be non-empty")
