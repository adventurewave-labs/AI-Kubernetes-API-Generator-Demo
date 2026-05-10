"""``ChecksumService`` domain service.

A tiny indirection over :meth:`Checksum.of` that exists for two reasons:

1. **Dependency injection / testing.** Domain classes such as
   :class:`ArtifactGenerator` accept a :class:`ChecksumService` so a
   test can substitute a deterministic stub (e.g. one that records the
   payloads it sees, or returns a canned checksum) without monkey-patching
   the :class:`Checksum` value object.
2. **Single point of evolution.** When we eventually add a second
   algorithm (sha512, BLAKE3, …) generators won't need to change — the
   policy lives here.

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §4.
"""

from __future__ import annotations

from ai_platform_generator.domain.values.checksum import Checksum


class ChecksumService:
    """Pure-function service that computes :class:`Checksum` digests."""

    def sha256_of(self, payload: bytes) -> Checksum:
        """Return a SHA-256 :class:`Checksum` of ``payload``.

        ``payload`` MUST be ``bytes`` — passing ``str`` would silently
        encode under the platform default and break determinism between
        platforms, so we type-check up front.
        """
        if not isinstance(payload, bytes):
            raise TypeError(
                f"payload must be bytes, got {type(payload).__name__}"
            )
        return Checksum.of(payload)
