"""Checksum value object.

A SHA-256 digest of an artefact's byte content. Used in the
``ProvenanceManifest`` to bind every emitted file to a tamper-evident
fingerprint.

See ``docs/ddd/04-tactical-design.md`` section 2.9 for the contract.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from ai_platform_generator.domain.errors import InvalidChecksum

# Lowercase hex, exactly 64 characters: SHA-256 produces 32 bytes ==
# 64 hex chars. We deliberately reject upper-case to keep the on-disk
# manifest format normalised.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Checksum:
    """An immutable, validated SHA-256 checksum.

    Parameters
    ----------
    algorithm:
        Currently only ``"sha256"`` is supported. Reserved as a field so
        we can add ``"sha512"`` later without breaking the wire format.
    value:
        The 64-character lowercase hex digest.
    """

    algorithm: Literal["sha256"]
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise InvalidChecksum(
                f"unsupported checksum algorithm {self.algorithm!r}; "
                "only 'sha256' is currently supported"
            )
        if not isinstance(self.value, str) or not _SHA256_RE.fullmatch(self.value):
            raise InvalidChecksum(
                f"checksum value {self.value!r} is not 64 lowercase hex characters"
            )

    def matches(self, payload: bytes) -> bool:
        """Return ``True`` iff ``payload``'s SHA-256 equals :attr:`value`."""
        return hashlib.sha256(payload).hexdigest() == self.value

    @classmethod
    def of(cls, payload: bytes) -> Checksum:
        """Compute a fresh SHA-256 ``Checksum`` for ``payload``."""
        return cls(algorithm="sha256", value=hashlib.sha256(payload).hexdigest())
