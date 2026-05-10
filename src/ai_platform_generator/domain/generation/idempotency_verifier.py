"""``IdempotencyVerifier`` — golden-test helper for byte-stable generation.

Per ``docs/ddd/bounded-contexts/03-artifact-generation.md`` §8 every
generator must be byte-deterministic given the same IR + target dir.
The verifier runs a generator ``runs`` times into separate temp
directories and asserts the byte content of each artefact (matched by
relative path) is identical across runs.

Usage::

    verifier = IdempotencyVerifier()
    verifier.verify_byte_stable(generator, ir, runs=3)

Non-deterministic paths (e.g. ``manifest.json`` if it embeds a
timestamp) can be skipped by passing ``ignore_paths`` — they are
matched as **suffixes** of the artefact's path because absolute paths
differ between temp dirs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import (
        OpenAPIDocument,
        RenderedArtifact,
    )
    from ai_platform_generator.domain.generation.artifact_generator import (
        ArtifactGenerator,
    )


class IdempotencyVerifier:
    """Run a generator multiple times and assert byte-stable output."""

    def verify_byte_stable(
        self,
        generator: ArtifactGenerator,
        ir: OpenAPIDocument,
        runs: int = 3,
        ignore_paths: tuple[str, ...] = (),
    ) -> None:
        """Assert every artefact is byte-identical across ``runs`` runs.

        Parameters
        ----------
        generator:
            The :class:`ArtifactGenerator` under test.
        ir:
            The OpenAPI IR to feed in.
        runs:
            Number of independent runs (≥ 2). Defaults to 3 — two is
            enough to detect drift but three catches the rare case
            where a generator alternates between two outputs.
        ignore_paths:
            Path *suffixes* whose bytes are excluded from comparison.
            Matched against the relative path each artefact records,
            because absolute paths embed the per-run temp dir.

        Raises
        ------
        AssertionError
            If any artefact's bytes differ across runs, if the set of
            relative paths differs, or if ``runs < 2``.
        """
        if runs < 2:
            raise AssertionError(
                f"verify_byte_stable requires runs >= 2, got {runs}"
            )

        captured: list[dict[str, bytes]] = []
        for _ in range(runs):
            with tempfile.TemporaryDirectory(prefix="idem-verifier-") as td:
                target = Path(td)
                artefacts = generator.generate(ir, target)
                captured.append(
                    self._index_by_relative_path(artefacts, target, ignore_paths)
                )

        # Compare every run to the first.
        baseline = captured[0]
        baseline_paths = set(baseline)
        for i, run_files in enumerate(captured[1:], start=1):
            run_paths = set(run_files)
            if run_paths != baseline_paths:
                only_baseline = sorted(baseline_paths - run_paths)
                only_run = sorted(run_paths - baseline_paths)
                raise AssertionError(
                    f"run #{i} produced a different set of files than run #0; "
                    f"only in #0: {only_baseline}; only in #{i}: {only_run}"
                )
            for rel_path, payload in run_files.items():
                if payload != baseline[rel_path]:
                    raise AssertionError(
                        f"non-deterministic output for {rel_path!r}: "
                        f"run #0 produced {len(baseline[rel_path])} bytes, "
                        f"run #{i} produced {len(payload)} bytes "
                        "(or differs in content)"
                    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _index_by_relative_path(
        artefacts: tuple[RenderedArtifact, ...],
        target: Path,
        ignore_paths: tuple[str, ...],
    ) -> dict[str, bytes]:
        """Return ``{relative_posix_path: payload}`` for ``artefacts``.

        Paths are normalised to POSIX so the comparison is platform
        portable. Any artefact whose relative path ends with one of the
        ``ignore_paths`` suffixes is skipped.
        """
        indexed: dict[str, bytes] = {}
        for art in artefacts:
            try:
                rel = art.path.relative_to(target)
            except ValueError:
                # Artefact written outside the target dir — keep the
                # absolute path as the key so we still detect drift.
                rel = art.path
            rel_str = rel.as_posix()
            if any(rel_str.endswith(suffix) for suffix in ignore_paths):
                continue
            indexed[rel_str] = art.payload
        return indexed
