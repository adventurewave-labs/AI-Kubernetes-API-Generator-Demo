"""OutputPath value object.

An allow-listed, traversal-checked filesystem destination for a
generated artifact.

See ``docs/ddd/04-tactical-design.md`` section 2.8 for the contract,
and ``docs/adr/0020-security-threat-model-and-hardening.md`` for the
underlying security requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_platform_generator.domain.errors import InvalidOutputPath


@dataclass(frozen=True, slots=True)
class OutputPath:
    """A safe, root-anchored output location.

    The ``root`` is resolved to an absolute path at construction time.
    The ``relative`` part must not contain any ``..`` components, and
    the resulting :attr:`full` path is asserted to lie inside ``root``.
    """

    root: Path
    relative: Path

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise InvalidOutputPath(f"root must be a Path, got {type(self.root)!r}")
        if not isinstance(self.relative, Path):
            raise InvalidOutputPath(
                f"relative must be a Path, got {type(self.relative)!r}"
            )
        if self.relative.is_absolute():
            raise InvalidOutputPath(
                f"relative path must not be absolute: {self.relative}"
            )
        if any(part == ".." for part in self.relative.parts):
            raise InvalidOutputPath(
                f"relative path must not contain '..' components: {self.relative}"
            )
        # Resolve root to an absolute path. frozen=True forbids regular
        # assignment, so we use object.__setattr__.
        object.__setattr__(self, "root", self.root.resolve())

        # Asserting the property contract eagerly catches symlink
        # escapes (e.g. relative='link' where link -> /etc).
        full = (self.root / self.relative).resolve()
        try:
            full.relative_to(self.root)
        except ValueError as exc:
            raise InvalidOutputPath(
                f"resolved path {full} escapes root {self.root}"
            ) from exc

    @property
    def full(self) -> Path:
        """The absolute, resolved path ``(root / relative)``.

        Asserted to lie inside ``root``; an internal :class:`AssertionError`
        is raised if a TOCTOU symlink change has caused that to no longer
        hold (the constructor verified it at creation time).
        """
        full = (self.root / self.relative).resolve()
        assert full == self.root or self.root in full.parents, (
            f"OutputPath.full {full} escaped root {self.root}"
        )
        return full
