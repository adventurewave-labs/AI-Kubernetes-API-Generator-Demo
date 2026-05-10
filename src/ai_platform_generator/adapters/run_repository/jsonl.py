"""Append-only JSONL :class:`RunRepository` adapter.

Implements an audit log of generation runs. Each appended run is
serialised to a single JSON object on its own line. The store is
deliberately **not** a full-state persistence layer: only a
projection of each :class:`GenerationRun` is recorded (id,
``started_at``, ``state``, ``intent.text_hash``, optional ``gvk``,
optional ``manifest_checksum``).

That projection is enough to:

* answer "what runs has this tool ever produced?";
* attribute log/event lines to a run by ``run_id``;
* tell the user which run wrote a particular ``ArtifactBundle``.

It is **not** enough to revive an in-memory :class:`GenerationRun`
aggregate with its attached :class:`OpenAPIDocument` /
:class:`ArtifactBundle`. The orchestrator already keeps the active
run in memory; reading the JSONL store reconstructs only the
projection. Callers wanting full-state replay must use a different
adapter (e.g. SQLite + bundle store cross-reference).

Format example (one per line)::

    {"run_id":"…","started_at":"2026-05-10T00:00:00+00:00",
     "state":"succeeded","intent_text_hash":"…","gvk":{"group":"…",
     "version":"…","kind":"…"},"manifest_checksum":"…"}
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ai_platform_generator.domain.aggregates.generation_run import (
    GenerationRun,
    RunState,
)
from ai_platform_generator.domain.values import Intent, RunId

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


_DEFAULT_PATH = Path(".platform-gen") / "runs.jsonl"


class JsonlRunRepository:
    """Append-only JSONL audit log of generation runs.

    Parameters
    ----------
    path:
        Destination file. Defaults to ``./.platform-gen/runs.jsonl``.
        The parent directory is created at construction time.

    Notes
    -----
    Reconstructing a :class:`GenerationRun` from this store loses the
    in-memory aggregates (``request``, ``ir``, ``bundle``,
    ``deployment``). The returned entity has them set to ``None``.
    Document this when consuming :meth:`get`/:meth:`latest`.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path: Path = path if path is not None else _DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def path(self) -> Path:
        """The configured destination path."""
        return self._path

    # ------------------------------------------------------------------
    # RunRepository protocol
    # ------------------------------------------------------------------
    def append(self, run: GenerationRun) -> None:
        """Append a JSON line capturing the projection of ``run``.

        Uses ``O_APPEND`` so concurrent appenders don't clobber each
        other (POSIX append-mode is atomic for writes ≤ ``PIPE_BUF``).
        ``fsync`` is called before close so the line survives a power
        loss.
        """
        line = (json.dumps(_run_to_dict(run), sort_keys=True) + "\n").encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self._path, flags, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    def get(self, run_id: RunId) -> GenerationRun:
        """Linear-scan for ``run_id``.

        See class-level note: only the projection is recoverable —
        ``request``, ``ir``, ``bundle``, and ``deployment`` are always
        ``None`` on the returned entity.
        """
        target = run_id.value
        for record in self._iter_records():
            if record.get("run_id") == target:
                return _run_from_dict(record)
        raise KeyError(f"no run with run_id {target!r} in {self._path}")

    def latest(self) -> GenerationRun | None:
        """Return the projection of the most recently appended run."""
        latest_record: dict[str, Any] | None = None
        for record in self._iter_records():
            latest_record = record
        if latest_record is None:
            return None
        return _run_from_dict(latest_record)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _iter_records(self) -> list[dict[str, Any]]:
        if not self._path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    out.append(cast("dict[str, Any]", record))
        return out


# ---------------------------------------------------------------------------
# Projection helpers — kept module-private; they are not part of the public API
# ---------------------------------------------------------------------------


def _run_to_dict(run: GenerationRun) -> dict[str, Any]:
    """Project a :class:`GenerationRun` to a JSON-friendly dict.

    Captures only:

    * ``run_id``
    * ``started_at`` (ISO-8601)
    * ``state``
    * ``intent_text_hash``
    * ``gvk`` (when ``request`` is attached)
    * ``manifest_checksum`` (when ``bundle`` is attached)

    Full aggregates are intentionally not serialised — see the module
    docstring.
    """
    payload: dict[str, Any] = {
        "run_id": run.id.value,
        "started_at": run.started_at.isoformat(),
        "state": run.state.value,
        "intent_text_hash": run.intent.text_hash(),
    }
    if run.request is not None:
        payload["gvk"] = {
            "group": run.request.gvk.group.value,
            "version": run.request.gvk.version.value,
            "kind": run.request.gvk.kind.value,
        }
    if run.bundle is not None and run.bundle.manifest is not None:
        # Use the manifest's first file checksum as a stable bundle
        # fingerprint when one exists; fall back to ``None`` if the
        # bundle has no files yet (shouldn't happen in practice).
        files = run.bundle.manifest.files
        if files:
            payload["manifest_checksum"] = files[0].checksum.value
    return payload


def _run_from_dict(data: dict[str, Any]) -> GenerationRun:
    """Reconstruct the projection-only :class:`GenerationRun`."""
    intent_text_hash = str(data.get("intent_text_hash", ""))
    started_raw = data.get("started_at")
    if not isinstance(started_raw, str):
        raise ValueError(f"unparseable started_at: {started_raw!r}")
    started = datetime.fromisoformat(started_raw)
    # The intent's raw text is not persisted (only its hash). We carry
    # the hash through as the intent text so callers can still cross-
    # reference, while keeping the ``Intent`` value object's invariants
    # satisfied.
    intent = Intent(text=intent_text_hash, submitted_at=started)
    state = RunState(str(data.get("state", "pending")))
    return GenerationRun(
        id=RunId(str(data["run_id"])),
        started_at=started,
        intent=intent,
        state=state,
    )


__all__ = ["JsonlRunRepository"]
