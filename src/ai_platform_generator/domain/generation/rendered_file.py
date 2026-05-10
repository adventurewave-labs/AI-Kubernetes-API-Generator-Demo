"""Intermediate ``_RenderedFile`` value type.

The bounded-context aggregates module owns ``RenderedArtifact``
(``path + bytes + mode + artefact_type + checksum``). Inside the
Template-Method lifecycle the ``_render`` step has only computed
``path`` + ``bytes`` — the checksum is computed in ``_finalise``. To
avoid re-using the public ``RenderedArtifact`` for an under-populated
state, we model the intermediate value as ``_RenderedFile`` here.

The leading underscore is intentional: callers outside the generation
package should never touch ``_RenderedFile``; they consume the public
``RenderedArtifact`` produced by ``ArtifactGenerator.generate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class _RenderedFile:
    """A path + bytes pair produced by a generator's ``_render`` step.

    Notes
    -----
    Intentionally minimal — no ``mode`` and no ``artefact_type``: those
    are added when the base class converts the tuple into
    ``RenderedArtifact`` instances. ``mode`` defaults to ``0o644`` in
    ``ArtifactGenerator._finalise``; ``artefact_type`` is read from the
    generator's class-level attribute.
    """

    path: Path
    payload: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError(f"path must be a Path, got {type(self.path).__name__}")
        if not isinstance(self.payload, bytes):
            raise TypeError(
                f"payload must be bytes, got {type(self.payload).__name__}"
            )
