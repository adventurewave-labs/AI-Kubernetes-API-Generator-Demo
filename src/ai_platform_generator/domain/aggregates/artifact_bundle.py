"""ArtifactBundle aggregate root.

The output of the Artifact Generation context: a sealed, checksum-bound
collection of rendered files plus a provenance manifest. See
``docs/ddd/04-tactical-design.md`` section 4.3.

Design notes
------------
* This module owns the **shape** of ``RenderedArtifact``,
  ``ProvenanceManifest`` and ``ArtifactType``. The *factory* that
  builds a ``ProvenanceManifest`` (capturing tool version, git SHA,
  generated_at) is owned by Agent G under
  ``domain/services/provenance_manifest_factory.py`` — we only define
  the data type here.
* The ``ChecksumService`` (Agent G) is the canonical path for producing
  ``Checksum``s. The aggregate calls
  :meth:`ai_platform_generator.domain.values.Checksum.matches` directly
  to verify pre-computed checksums; it does not compute them.
* All paths are stored as :class:`pathlib.Path` instances. Determinism
  is the load-bearing invariant: a bundle's ``files`` tuple iterates in
  insertion order, which the caller is required to keep stable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import ChecksumMismatch
from ai_platform_generator.domain.errors.domain_validation import DomainValidationError
from ai_platform_generator.domain.values import Checksum, ProviderMode, RunId


class InvalidArtifactBundle(DomainValidationError):
    """The :class:`ArtifactBundle` aggregate failed an invariant check."""

    code = "E_DOMAIN_INVALID_ARTIFACT_BUNDLE"


class InvalidProvenanceManifest(DomainValidationError):
    """The :class:`ProvenanceManifest` failed an invariant check."""

    code = "E_DOMAIN_INVALID_PROVENANCE_MANIFEST"


class ArtifactType(StrEnum):
    """The set of artefact kinds the generator can produce.

    Listed in the order they appear on disk so a bundle's printout
    matches the on-disk layout.
    """

    OPENAPI = "openapi"
    CRD = "crd"
    INSTANCE = "instance"
    GO_CONTROLLER = "go_controller"
    MCP_SERVER = "mcp_server"
    KUSTOMIZATION = "kustomization"


# ---------------------------------------------------------------------------
# RenderedArtifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    """A single rendered file inside an :class:`ArtifactBundle`.

    Parameters
    ----------
    path:
        Path **relative** to the bundle's ``target_dir``. Must not be
        absolute and must not contain ``..`` components.
    payload:
        The raw byte content. Stored verbatim — no re-encoding. Named
        ``payload`` (rather than ``bytes_payload``) so the same name
        threads through ``_RenderedFile.payload`` in the generation
        package and the public ``RenderedArtifact.payload`` here —
        avoiding a needless rename at every boundary.
    mode:
        POSIX file mode (e.g. ``0o644``). Stored so the persistence
        adapter can chmod the file on write.
    artefact_type:
        Which kind of artefact this is (drives downstream validation).
    checksum:
        SHA-256 digest of ``payload``. Verified at construction
        time — a mismatch raises :class:`ChecksumMismatch`.
    """

    path: Path
    payload: bytes
    mode: int
    artefact_type: ArtifactType
    checksum: Checksum

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise InvalidArtifactBundle(
                f"RenderedArtifact.path must be a Path, got {type(self.path)!r}"
            )
        if any(part == ".." for part in self.path.parts):
            raise InvalidArtifactBundle(
                f"RenderedArtifact.path must not contain '..' components: {self.path!r}"
            )
        if not isinstance(self.payload, bytes):
            raise InvalidArtifactBundle(
                "RenderedArtifact.payload must be bytes, got "
                f"{type(self.payload)!r}"
            )
        if not isinstance(self.mode, int) or self.mode < 0 or self.mode > 0o7777:
            raise InvalidArtifactBundle(
                f"RenderedArtifact.mode must be a POSIX mode, got {self.mode!r}"
            )
        if not isinstance(self.artefact_type, ArtifactType):
            raise InvalidArtifactBundle(
                "RenderedArtifact.artefact_type must be an ArtifactType, got "
                f"{type(self.artefact_type)!r}"
            )
        if not isinstance(self.checksum, Checksum):
            raise InvalidArtifactBundle(
                "RenderedArtifact.checksum must be a Checksum, got "
                f"{type(self.checksum)!r}"
            )
        if not self.checksum.matches(self.payload):
            raise ChecksumMismatch(
                "RenderedArtifact checksum does not match its payload "
                f"(path={self.path!r})"
            )


# ---------------------------------------------------------------------------
# ProvenanceManifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A (path, checksum) pair recorded in the provenance manifest."""

    path: Path
    checksum: Checksum

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise InvalidProvenanceManifest(
                f"ArtifactRef.path must be a Path, got {type(self.path)!r}"
            )
        if not isinstance(self.checksum, Checksum):
            raise InvalidProvenanceManifest(
                f"ArtifactRef.checksum must be a Checksum, got {type(self.checksum)!r}"
            )


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    """Tamper-evident record of a generation run.

    See ``docs/ddd/04-tactical-design.md`` section 4.3.

    The factory that constructs a ``ProvenanceManifest`` (capturing
    tool/git/run metadata at sealing time) is owned by another agent
    under ``domain/services/provenance_manifest_factory.py``; this
    class only defines the value shape and its invariants.
    """

    run_id: RunId
    tool_version: str
    git_sha: str
    generated_at: datetime
    request: CodegenRequest
    provider_mode: ProviderMode
    model_id: str | None
    files: tuple[ArtifactRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise InvalidProvenanceManifest(
                f"run_id must be a RunId, got {type(self.run_id)!r}"
            )
        if not isinstance(self.tool_version, str) or not self.tool_version.strip():
            raise InvalidProvenanceManifest(
                f"tool_version must be a non-blank str, got {self.tool_version!r}"
            )
        if not isinstance(self.git_sha, str) or not self.git_sha.strip():
            raise InvalidProvenanceManifest(
                f"git_sha must be a non-blank str, got {self.git_sha!r}"
            )
        if not isinstance(self.generated_at, datetime):
            raise InvalidProvenanceManifest(
                f"generated_at must be a datetime, got {type(self.generated_at)!r}"
            )
        if not isinstance(self.request, CodegenRequest):
            raise InvalidProvenanceManifest(
                f"request must be a CodegenRequest, got {type(self.request)!r}"
            )
        if not isinstance(self.provider_mode, ProviderMode):
            raise InvalidProvenanceManifest(
                "provider_mode must be a ProviderMode, got "
                f"{type(self.provider_mode)!r}"
            )
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise InvalidProvenanceManifest(
                f"model_id must be a str or None, got {type(self.model_id)!r}"
            )
        if not isinstance(self.files, tuple):
            raise InvalidProvenanceManifest(
                f"files must be a tuple, got {type(self.files)!r}"
            )
        for entry in self.files:
            if not isinstance(entry, ArtifactRef):
                raise InvalidProvenanceManifest(
                    f"files entries must be ArtifactRef, got {type(entry)!r}"
                )

    def file_paths(self) -> tuple[Path, ...]:
        """Convenience accessor for cross-checking against an artifact bundle."""
        return tuple(ref.path for ref in self.files)


# ---------------------------------------------------------------------------
# ArtifactBundle aggregate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    """Aggregate root: a sealed bundle of rendered artefacts.

    Parameters
    ----------
    run_id:
        Identifier of the generation run that produced this bundle.
    target_dir:
        Absolute output directory (where the persistence adapter writes).
    files:
        A tuple of :class:`RenderedArtifact`, in the order they should
        appear on disk.
    manifest:
        The :class:`ProvenanceManifest` describing this bundle.

    Invariants enforced in ``__post_init__``:

    1. ``target_dir`` is absolute.
    2. Every ``RenderedArtifact.path`` is unique within ``files``.
    3. Every ``RenderedArtifact.checksum`` matches its bytes (already
       checked by ``RenderedArtifact``, re-verified here for safety).
    4. ``manifest.files`` exactly matches ``files`` by ``(path,
       checksum)`` set.
    5. ``manifest.run_id`` matches ``run_id``.
    """

    run_id: RunId
    target_dir: Path
    files: tuple[RenderedArtifact, ...]
    manifest: ProvenanceManifest = field()

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise InvalidArtifactBundle(
                f"run_id must be a RunId, got {type(self.run_id)!r}"
            )
        if not isinstance(self.target_dir, Path):
            raise InvalidArtifactBundle(
                f"target_dir must be a Path, got {type(self.target_dir)!r}"
            )
        if not self.target_dir.is_absolute():
            raise InvalidArtifactBundle(
                f"target_dir must be absolute, got {self.target_dir!r}"
            )
        if not isinstance(self.files, tuple):
            raise InvalidArtifactBundle(
                f"files must be a tuple, got {type(self.files)!r}"
            )
        seen: set[Path] = set()
        for art in self.files:
            if not isinstance(art, RenderedArtifact):
                raise InvalidArtifactBundle(
                    f"files entries must be RenderedArtifact, got {type(art)!r}"
                )
            if art.path in seen:
                raise InvalidArtifactBundle(
                    f"duplicate artefact path {art.path!r} in bundle"
                )
            seen.add(art.path)
            # Re-verify (ChecksumMismatch raised here if tampering).
            if not art.checksum.matches(art.payload):
                raise ChecksumMismatch(
                    f"artefact {art.path!r} checksum does not match its bytes"
                )

        if not isinstance(self.manifest, ProvenanceManifest):
            raise InvalidArtifactBundle(
                f"manifest must be a ProvenanceManifest, got {type(self.manifest)!r}"
            )
        if self.manifest.run_id != self.run_id:
            raise InvalidArtifactBundle(
                "manifest.run_id does not match bundle.run_id"
            )

        bundle_pairs: set[tuple[Path, str]] = {
            (art.path, art.checksum.value) for art in self.files
        }
        manifest_pairs: set[tuple[Path, str]] = {
            (ref.path, ref.checksum.value) for ref in self.manifest.files
        }
        if bundle_pairs != manifest_pairs:
            raise InvalidArtifactBundle(
                "manifest.files does not match bundle.files (path+checksum mismatch)"
            )

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    def by_path(self, path: Path) -> RenderedArtifact | None:
        """Return the artefact at ``path`` or ``None`` if not found."""
        for art in self.files:
            if art.path == path:
                return art
        return None

    def of_type(
        self, artefact_type: ArtifactType
    ) -> tuple[RenderedArtifact, ...]:
        """Return all artefacts of a given :class:`ArtifactType`."""
        return tuple(art for art in self.files if art.artefact_type is artefact_type)


# ---------------------------------------------------------------------------
# Helpers used by tests / factories
# ---------------------------------------------------------------------------


def make_artifact_refs(
    artifacts: Iterable[RenderedArtifact],
) -> tuple[ArtifactRef, ...]:
    """Build a tuple of :class:`ArtifactRef` from artefacts.

    Used by the manifest factory and by tests; kept here so the
    aggregate file is the single source of truth for the (path,
    checksum) pairing.
    """
    return tuple(ArtifactRef(path=art.path, checksum=art.checksum) for art in artifacts)


__all__: list[str] = [
    "ArtifactBundle",
    "ArtifactRef",
    "ArtifactType",
    "InvalidArtifactBundle",
    "InvalidProvenanceManifest",
    "ProvenanceManifest",
    "RenderedArtifact",
    "make_artifact_refs",
]


# Silence "unused" warnings for `Any` (kept for forward-compatible factories
# that may attach arbitrary metadata).
_: Any = None
