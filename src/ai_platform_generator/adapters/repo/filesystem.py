"""Filesystem-backed :class:`ArtifactRepository` adapter.

See:

* ADR-0013 (filesystem as the canonical artifact store)
* ADR-0020 §3 (filesystem hygiene — path traversal, file modes)
* ``docs/ddd/07-anti-corruption-layers.md`` §3.3

Design notes
------------
* The configured ``root`` is resolved to an absolute :class:`Path` at
  construction; every subsequent path operation is anchored to this
  resolved root.
* Writes are *atomic*: each artefact is staged at ``<path>.tmp`` and
  promoted with :func:`os.replace` so a crash mid-write never leaves a
  partial file in place. The temporary file is removed on failure.
* Persisted ``manifest.json`` files are written with mode ``0o600`` (the
  manifest may contain host paths and identifying metadata); other
  artefacts use ``0o644``.
* Path safety: every resolved write target is verified to lie inside
  the bundle's ``target_dir`` (and the ``target_dir`` itself inside
  ``root``) using :meth:`pathlib.Path.is_relative_to`. ``..`` components,
  absolute relative paths, and symlinks pointing outside the root are
  rejected with :class:`ArtifactWriteFailed` carrying the
  ``E_ARTIFACT_PATH_TRAVERSAL`` code.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.aggregates.artifact_bundle import (
    ArtifactBundle,
    ArtifactRef,
    ArtifactType,
    ProvenanceManifest,
    RenderedArtifact,
)
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import (
    ArtifactWriteFailed,
    ChecksumMismatch,
)
from ai_platform_generator.domain.values import Checksum, ProviderMode, RunId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from datetime import datetime


_PATH_TRAVERSAL_CODE = "E_ARTIFACT_PATH_TRAVERSAL"
_MANIFEST_FILENAME = "manifest.json"
_ARTEFACT_MODE = 0o644
_MANIFEST_MODE = 0o600


def _safe_resolve(root: Path, candidate: Path) -> Path:
    """Resolve ``candidate`` and assert it is inside ``root``.

    ``root`` MUST already be absolute and resolved. ``candidate`` may be
    absolute (it is resolved as-is) or relative (resolved relative to
    ``root``). ``..`` components and symlinks pointing outside ``root``
    are rejected.

    Raises
    ------
    ArtifactWriteFailed
        With ``code`` set to :data:`_PATH_TRAVERSAL_CODE` if the resolved
        path escapes ``root``.
    """
    if any(part == ".." for part in candidate.parts):
        exc = ArtifactWriteFailed(
            f"path {candidate} contains '..' components and was rejected"
        )
        exc.code = _PATH_TRAVERSAL_CODE
        raise exc

    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
    else:
        resolved = (root / candidate).resolve(strict=False)

    if not (resolved == root or resolved.is_relative_to(root)):
        exc = ArtifactWriteFailed(
            f"path {resolved} escapes configured root {root}"
        )
        exc.code = _PATH_TRAVERSAL_CODE
        raise exc
    return resolved


class FilesystemArtifactRepository:
    """Persist :class:`ArtifactBundle` aggregates under a configured root.

    Parameters
    ----------
    root:
        The configured output root. Resolved to an absolute path at
        construction. Every artefact write is asserted to land inside
        this directory.
    create_root:
        If True (default), create ``root`` (and parents) when it does
        not yet exist.
    umask:
        Documented for completeness — the adapter does **not** apply a
        process-wide umask; explicit ``chmod`` calls set the
        per-artefact mode. Kept on the constructor so future
        deployments may opt-in via :func:`os.umask` outside the adapter.
    """

    def __init__(
        self,
        root: Path,
        *,
        create_root: bool = True,
        umask: int = 0o022,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError(
                f"root must be a pathlib.Path, got {type(root)!r}"
            )
        resolved = root.resolve(strict=False)
        if create_root:
            resolved.mkdir(parents=True, exist_ok=True)
        elif not resolved.is_dir():
            exc = ArtifactWriteFailed(
                f"configured root {resolved} does not exist"
            )
            raise exc
        self._root: Path = resolved
        self._umask: int = umask

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        """The resolved, absolute output root."""
        return self._root

    # ------------------------------------------------------------------
    # ArtifactRepository protocol
    # ------------------------------------------------------------------
    def save(self, bundle: ArtifactBundle) -> None:
        """Persist ``bundle`` under :attr:`root`.

        Atomic, traversal-safe, checksum-verified.
        """
        target_dir = _safe_resolve(self._root, bundle.target_dir)
        # Belt-and-braces — _safe_resolve already enforces this, but the
        # explicit assert makes the invariant readable.
        if not (target_dir == self._root or target_dir.is_relative_to(self._root)):
            exc = ArtifactWriteFailed(
                f"target_dir {target_dir} escapes root {self._root}"
            )
            exc.code = _PATH_TRAVERSAL_CODE
            raise exc

        target_dir.mkdir(parents=True, exist_ok=True)

        written_paths: list[Path] = []
        try:
            for artefact in bundle.files:
                # Reject absolute artefact paths or '..' components up-front
                # to give a precise error before _safe_resolve does the
                # final check.
                if artefact.path.is_absolute():
                    exc = ArtifactWriteFailed(
                        f"artefact path {artefact.path} must be relative to "
                        "the bundle target_dir"
                    )
                    exc.code = _PATH_TRAVERSAL_CODE
                    raise exc
                full = _safe_resolve(target_dir, artefact.path)
                _atomic_write_bytes(
                    full,
                    artefact.payload,
                    mode=(
                        _MANIFEST_MODE
                        if full.name == _MANIFEST_FILENAME
                        else artefact.mode or _ARTEFACT_MODE
                    ),
                )
                written_paths.append(full)

            manifest_path = target_dir / _MANIFEST_FILENAME
            manifest_bytes = _serialise_manifest(bundle.manifest)
            _atomic_write_bytes(manifest_path, manifest_bytes, mode=_MANIFEST_MODE)
            written_paths.append(manifest_path)

            # Verify on-disk checksums match what the bundle declared.
            for artefact in bundle.files:
                full = target_dir / artefact.path
                disk_bytes = full.read_bytes()
                if not artefact.checksum.matches(disk_bytes):
                    raise ChecksumMismatch(
                        f"on-disk checksum mismatch for {full}"
                    )
        except ChecksumMismatch:
            raise
        except ArtifactWriteFailed:
            raise
        except OSError as exc:
            wrapped = ArtifactWriteFailed(
                f"failed to write bundle under {target_dir}: {exc}",
                cause=exc,
            )
            raise wrapped from exc

    def load(self, run_id: RunId) -> ArtifactBundle:
        """Reconstruct a previously-persisted :class:`ArtifactBundle`.

        Walks every ``manifest.json`` under :attr:`root`, parses it, and
        returns the bundle whose manifest carries the requested
        ``run_id``. Bytes are re-read from disk; checksums are
        re-validated by ``RenderedArtifact.__post_init__``.
        """
        for manifest_path in sorted(self._root.glob("**/" + _MANIFEST_FILENAME)):
            try:
                raw = json.loads(manifest_path.read_bytes().decode("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            if raw.get("run_id") != run_id.value:
                continue
            return _bundle_from_manifest_on_disk(manifest_path, raw, run_id)
        raise KeyError(f"no bundle with run_id {run_id.value!r} under {self._root}")

    def exists(self, run_id: RunId) -> bool:
        """Return True iff a manifest under :attr:`root` references ``run_id``."""
        for manifest_path in self._root.glob("**/" + _MANIFEST_FILENAME):
            try:
                raw = json.loads(manifest_path.read_bytes().decode("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(raw, dict) and raw.get("run_id") == run_id.value:
                return True
        return False


# ---------------------------------------------------------------------------
# Helpers — atomic write + manifest (de)serialisation
# ---------------------------------------------------------------------------


def _atomic_write_bytes(path: Path, payload: bytes, *, mode: int) -> None:
    """Atomically write ``payload`` to ``path`` and chmod to ``mode``.

    Strategy: write to ``path.with_suffix(suffix + '.tmp')`` then
    :func:`os.replace`. fsync the temporary file before promotion so a
    crash between write and replace cannot leave partial content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        # Clean up the partial temp file before propagating.
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    try:
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    os.chmod(path, mode)


def _serialise_manifest(manifest: ProvenanceManifest) -> bytes:
    """Serialise ``manifest`` to deterministic UTF-8 bytes.

    Uses ``json.dumps`` with ``sort_keys=True`` and ``indent=2`` plus a
    trailing newline so that golden-file tests are stable across Python
    versions.
    """
    payload = _manifest_to_dict(manifest)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _manifest_to_dict(manifest: ProvenanceManifest) -> dict[str, Any]:
    """Convert a :class:`ProvenanceManifest` to a JSON-friendly dict."""
    return {
        "run_id": manifest.run_id.value,
        "tool_version": manifest.tool_version,
        "git_sha": manifest.git_sha,
        "generated_at": manifest.generated_at.isoformat(),
        "request": manifest.request.to_dict(),
        "provider_mode": manifest.provider_mode.value,
        "model_id": manifest.model_id,
        "files": [
            {
                "path": str(ref.path),
                "checksum": {
                    "algorithm": ref.checksum.algorithm,
                    "value": ref.checksum.value,
                },
            }
            for ref in manifest.files
        ],
    }


def _manifest_from_dict(
    data: dict[str, Any],
    *,
    artefact_types: dict[str, ArtifactType] | None = None,
) -> ProvenanceManifest:
    """Reconstruct a :class:`ProvenanceManifest` from :func:`_manifest_to_dict` output."""
    from datetime import datetime as _dt

    refs = tuple(
        ArtifactRef(
            path=Path(str(item["path"])),
            checksum=Checksum(
                algorithm=str(item["checksum"]["algorithm"]),  # type: ignore[arg-type]
                value=str(item["checksum"]["value"]),
            ),
        )
        for item in data.get("files", [])
    )
    generated_at_raw = data.get("generated_at")
    generated_at: datetime
    if isinstance(generated_at_raw, str):
        generated_at = _dt.fromisoformat(generated_at_raw)
    else:  # pragma: no cover - defensive
        raise ValueError(f"unparseable generated_at: {generated_at_raw!r}")

    request = CodegenRequest.from_dict(data["request"])
    provider_mode = ProviderMode(str(data.get("provider_mode", "live")))
    model_id_raw = data.get("model_id")
    model_id = None if model_id_raw is None else str(model_id_raw)

    return ProvenanceManifest(
        run_id=RunId(str(data["run_id"])),
        tool_version=str(data["tool_version"]),
        git_sha=str(data["git_sha"]),
        generated_at=generated_at,
        request=request,
        provider_mode=provider_mode,
        model_id=model_id,
        files=refs,
    )


def _bundle_from_manifest_on_disk(
    manifest_path: Path,
    raw: dict[str, Any],
    run_id: RunId,
) -> ArtifactBundle:
    """Reconstruct an :class:`ArtifactBundle` rooted at the manifest's directory."""
    target_dir = manifest_path.parent.resolve()
    manifest = _manifest_from_dict(raw)
    artefacts: list[RenderedArtifact] = []
    for ref in manifest.files:
        full = target_dir / ref.path
        payload = full.read_bytes()
        artefacts.append(
            RenderedArtifact(
                path=ref.path,
                payload=payload,
                mode=_ARTEFACT_MODE,
                artefact_type=_infer_artefact_type(ref.path),
                checksum=ref.checksum,
            )
        )
    return ArtifactBundle(
        run_id=run_id,
        target_dir=target_dir,
        files=tuple(artefacts),
        manifest=manifest,
    )


def _infer_artefact_type(path: Path) -> ArtifactType:
    """Best-effort artefact-type classification for on-disk reconstruction.

    The on-disk format does not record :class:`ArtifactType` per file —
    callers reconstructing a bundle from disk fall back to a heuristic
    based on filename. ``OPENAPI`` is a sensible default that keeps
    downstream code paths lit even if the heuristic misses.
    """
    name = path.name.lower()
    if name.endswith(".crd.yaml") or "crd" in name:
        return ArtifactType.CRD
    if name.endswith(".instance.yaml") or "instance" in name:
        return ArtifactType.INSTANCE
    if name.endswith(".go") or "controller" in str(path).lower():
        return ArtifactType.GO_CONTROLLER
    if "mcp" in str(path).lower():
        return ArtifactType.MCP_SERVER
    if "kustomization" in name:
        return ArtifactType.KUSTOMIZATION
    return ArtifactType.OPENAPI


__all__ = [
    "FilesystemArtifactRepository",
    "_safe_resolve",
]
