"""``ProvenanceManifestFactory`` — assemble the bundle's provenance manifest.

The :class:`ProvenanceManifest` aggregate is owned by Agent E (sibling
wave). This factory takes everything *outside* the generator hierarchy
that the manifest needs — the run id, the originating
:class:`CodegenRequest`, the provider mode and model, the rendered
files, plus a clock — and assembles the manifest in one place.

Tool / git metadata
-------------------
``tool_version``
    Read from :data:`ai_platform_generator.__version__`.

``git_sha``
    Read from ``git rev-parse HEAD`` first; if that fails (e.g. running
    from a wheel) we fall back to the ``AI_PLATFORM_GENERATOR_GIT_SHA``
    environment variable; if that is also unset we record ``"unknown"``.
    The factory never raises on a missing git binary — provenance must
    survive the ``git`` command being absent.

See ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §7.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import ai_platform_generator as _pkg

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        CodegenRequest,
        ProvenanceManifest,
        RenderedArtifact,
    )
    from ai_platform_generator.domain.values.provider_mode import ProviderMode
    from ai_platform_generator.domain.values.run_id import RunId
    from ai_platform_generator.ports.clock import Clock


_GIT_SHA_ENV = "AI_PLATFORM_GENERATOR_GIT_SHA"
_UNKNOWN_GIT_SHA = "unknown"


class ProvenanceManifestFactory:
    """Builds a :class:`ProvenanceManifest` from a sealed bundle's parts."""

    def create(
        self,
        run_id: RunId,
        request: CodegenRequest,
        provider_mode: ProviderMode,
        model_id: str | None,
        files: list[RenderedArtifact],
        clock: Clock,
    ) -> ProvenanceManifest:
        """Assemble the provenance manifest.

        Parameters
        ----------
        run_id:
            Stable identity of the generation run.
        request:
            The originating :class:`CodegenRequest`.
        provider_mode:
            Live vs demo — recorded for replay/audit.
        model_id:
            LLM model identifier when ``provider_mode`` is live; ``None``
            for demo runs.
        files:
            The full list of rendered artefacts, after checksumming.
        clock:
            Time source — abstracted so golden tests can pin
            ``generated_at``.
        """
        # Lazy import: aggregates module is owned by Agent E.
        from ai_platform_generator.domain.aggregates import ProvenanceManifest
        from ai_platform_generator.domain.aggregates.artifact_bundle import (
            make_artifact_refs,
        )

        if not isinstance(files, list):
            raise TypeError(
                f"files must be a list, got {type(files).__name__}"
            )

        return ProvenanceManifest(
            run_id=run_id,
            tool_version=self._tool_version(),
            git_sha=self._git_sha(),
            generated_at=clock.now(),
            request=request,
            provider_mode=provider_mode,
            model_id=model_id,
            files=make_artifact_refs(files),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _tool_version() -> str:
        """Return ``ai_platform_generator.__version__`` (default ``"0.0.0"``)."""
        version = getattr(_pkg, "__version__", None)
        if not isinstance(version, str) or not version:
            return "0.0.0"
        return version

    @staticmethod
    def _git_sha() -> str:
        """Best-effort git revision lookup.

        Order of resolution:

        1. ``git rev-parse HEAD`` (subprocess, no shell). Any non-zero
           exit, missing binary, or :class:`OSError` → fall through.
        2. ``$AI_PLATFORM_GENERATOR_GIT_SHA`` — useful in CI / Docker
           images where ``.git`` is intentionally absent.
        3. The literal string ``"unknown"``.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except (FileNotFoundError, OSError):
            result = None

        if result is not None and result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha

        env_sha = os.environ.get(_GIT_SHA_ENV, "").strip()
        if env_sha:
            return env_sha

        return _UNKNOWN_GIT_SHA
