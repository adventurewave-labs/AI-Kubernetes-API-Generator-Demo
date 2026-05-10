"""``ArtifactGenerationService`` — application service for Phase 3.

Realises ``docs/ddd/06-application-services.md`` §6.3.

The service:

1. Iterates the configured generators in stable order.
2. Collects every ``RenderedArtifact`` they produce.
3. Computes a ``ProvenanceManifest`` (tool version, git SHA, generated_at).
4. Persists the bundle through the ``ArtifactRepository`` port.
5. Emits ``GenerationPlanned`` / ``ArtifactGenerated`` /
   ``ArtifactBundleSealed`` events.

The ``ArtifactGenerator`` ``Protocol`` is defined locally so the service
can be unit-tested with fake generators while Agent G's base class is
in flight. Once Agent G publishes the canonical ``ArtifactGenerator``
under ``domain.generation`` we'll replace this local definition with a
direct re-export.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ai_platform_generator import __version__ as _TOOL_VERSION
from ai_platform_generator.domain.events import (
    ArtifactBundleSealed,
    ArtifactGenerated,
    GenerationPlanned,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        ArtifactBundle,
        CodegenRequest,
        OpenAPIDocument,
        ProvenanceManifest,
        RenderedArtifact,
    )
    from ai_platform_generator.domain.values import RunId
    from ai_platform_generator.ports import (
        ArtifactRepository,
        Clock,
        TelemetrySink,
    )


# TODO(wave-2-agent-g): replace with ``from ai_platform_generator.domain.generation
#   import ArtifactGenerator`` once Agent G's base class lands.
@runtime_checkable
class ArtifactGenerator(Protocol):
    """Protocol every concrete generator implements.

    A generator's ``generate`` method takes the IR and a target
    directory and returns the list of ``RenderedArtifact``s it produced.
    The orchestrating service does *not* call ``_plan`` / ``_render`` /
    ``_post_process`` directly — those are template-method internals.
    """

    name: str

    def generate(
        self, ir: OpenAPIDocument, target: Path
    ) -> list[RenderedArtifact]:
        """Render every artefact this generator owns into ``target``."""

    def expected_paths(
        self, ir: OpenAPIDocument, target: Path
    ) -> list[Path]:
        """Return the paths this generator *would* write (for planning events)."""


class ArtifactGenerationService:
    """Run all generators against an IR and seal the resulting bundle."""

    def __init__(
        self,
        repo: ArtifactRepository,
        events: TelemetrySink,
        clock: Clock,
        generators: list[ArtifactGenerator] | None = None,
    ) -> None:
        self._repo = repo
        self._events = events
        self._clock = clock
        # Stable order: tests assert events are emitted in registration order.
        self._generators: list[ArtifactGenerator] = list(generators or [])

    def run(
        self,
        ir: OpenAPIDocument,
        request: CodegenRequest,
        target_dir: Path,
        *,
        run_id: RunId,
    ) -> ArtifactBundle:
        """Generate, persist, and seal the bundle for ``run_id``."""
        rendered: list[RenderedArtifact] = []
        for gen in self._generators:
            self._events.emit(
                GenerationPlanned.make(
                    run_id=run_id,
                    payload={
                        "generator": gen.name,
                        "expected_paths": [
                            str(p)
                            for p in _expected_paths(gen, ir, target_dir)
                        ],
                    },
                )
            )
            files = list(gen.generate(ir, target_dir))
            for file in files:
                self._events.emit(
                    ArtifactGenerated.make(
                        run_id=run_id,
                        payload={
                            "artefact_type": _artefact_type_value(file),
                            "path": str(getattr(file, "path", "")),
                            "checksum": _checksum_value(file),
                        },
                    )
                )
            rendered.extend(files)

        manifest = self._build_manifest(
            run_id=run_id,
            request=request,
            files=rendered,
        )

        bundle = _make_bundle(
            run_id=run_id,
            target_dir=target_dir,
            files=rendered,
            manifest=manifest,
        )

        self._repo.save(bundle)

        self._events.emit(
            ArtifactBundleSealed.make(
                run_id=run_id,
                payload={
                    "manifest_checksum": _manifest_checksum(manifest),
                    "file_count": len(rendered),
                    "target_dir": str(target_dir),
                },
            )
        )
        return bundle

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_manifest(
        self,
        *,
        run_id: RunId,
        request: CodegenRequest,
        files: list[RenderedArtifact],
    ) -> ProvenanceManifest:
        return _make_manifest(
            run_id=run_id,
            tool_version=_TOOL_VERSION,
            git_sha=_safe_git_sha(),
            generated_at=self._clock.now(),
            request=request,
            provider_mode=request.provider_mode,
            files=files,
            model_id=None,
        )


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _safe_git_sha() -> str:
    """Best-effort ``git rev-parse HEAD``; ``"unknown"`` outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):  # pragma: no cover
        return "unknown"
    if out.returncode != 0:
        return "unknown"
    return out.stdout.strip() or "unknown"


def _expected_paths(
    gen: ArtifactGenerator, ir: OpenAPIDocument, target: Path
) -> list[Path]:
    """Return the planning paths advertised by ``gen``, if any."""
    fn = getattr(gen, "expected_paths", None)
    if fn is None:
        return []
    try:
        return [Path(p) for p in fn(ir, target)]
    except Exception:  # pragma: no cover - planning is best-effort
        return []


def _artefact_type_value(file: Any) -> str:
    """Best-effort wire form of the ``artefact_type`` enum on ``file``."""
    art = getattr(file, "artefact_type", None)
    if art is None:
        return ""
    val = getattr(art, "value", None)
    return str(val if val is not None else art)


def _checksum_value(file: Any) -> str:
    """Best-effort string form of a file's checksum."""
    cs = getattr(file, "checksum", None)
    if cs is None:
        return ""
    return getattr(cs, "value", str(cs))


def _manifest_checksum(manifest: Any) -> str:
    """Compute a stable hash over the manifest's ``(path, checksum)`` pairs.

    The aggregate doesn't expose a self-checksum; the orchestrator and
    persistence layer derive one from the immutable refs. We sort by
    path so the digest is order-stable.
    """
    import hashlib

    files = getattr(manifest, "files", ())
    h = hashlib.sha256()
    for ref in sorted(files, key=lambda r: str(getattr(r, "path", ""))):
        h.update(str(getattr(ref, "path", "")).encode("utf-8"))
        h.update(b"\0")
        cs = getattr(ref, "checksum", None)
        h.update(getattr(cs, "value", "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


# Manifest / bundle factories live as module-private helpers so the
# service stays decoupled from the concrete aggregate constructors.
# Once Agent G publishes typed factories, replace these with direct
# imports.


def _make_manifest(
    *,
    run_id: RunId,
    tool_version: str,
    git_sha: str,
    generated_at: Any,
    request: CodegenRequest,
    provider_mode: Any,
    files: list[RenderedArtifact],
    model_id: str | None,
) -> ProvenanceManifest:
    """Construct a :class:`ProvenanceManifest` from rendered artefacts.

    Uses :func:`make_artifact_refs` to translate ``RenderedArtifact`` into
    the ``(path, checksum)`` pairs the manifest stores.
    """
    from ai_platform_generator.domain.aggregates.artifact_bundle import (
        ProvenanceManifest as _PM,
    )
    from ai_platform_generator.domain.aggregates.artifact_bundle import (
        make_artifact_refs,
    )

    return _PM(
        run_id=run_id,
        tool_version=tool_version,
        git_sha=git_sha,
        generated_at=generated_at,
        request=request,
        provider_mode=provider_mode,
        model_id=model_id,
        files=make_artifact_refs(files),
    )


def _make_bundle(
    *,
    run_id: RunId,
    target_dir: Path,
    files: list[RenderedArtifact],
    manifest: ProvenanceManifest,
) -> ArtifactBundle:
    """Construct an :class:`ArtifactBundle` aggregate."""
    from ai_platform_generator.domain.aggregates.artifact_bundle import (
        ArtifactBundle as _AB,
    )

    return _AB(
        run_id=run_id,
        target_dir=target_dir,
        files=tuple(files),
        manifest=manifest,
    )
