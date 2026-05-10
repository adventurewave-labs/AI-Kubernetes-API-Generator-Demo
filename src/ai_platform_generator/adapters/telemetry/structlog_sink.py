"""Structlog-backed :class:`TelemetrySink`.

Renders :class:`DomainEvent`s either as Rich-friendly key/value lines
(``mode="tty"``), as one JSON object per line (``mode="json"``), or
silently drops them (``mode="quiet"``).

Implements ADR-0017 §"Telemetry sinks" + the redaction commitment in
ADR-0020 §"Hardening commitments — Secret hygiene": every payload is
passed through a :class:`SecretRedactor` before structlog ever sees it.
Metric side-effects are produced via :class:`MetricsRecorder` if one is
supplied — the sink does not store metrics itself; that's the caller's
responsibility per ``docs/ddd/bounded-contexts/06-observability.md``
§7.
"""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING, Any, Literal

import structlog

from ai_platform_generator.domain.observability.redaction import (
    RedactionPolicy,
    SecretRedactor,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent
    from ai_platform_generator.domain.observability.metrics import MetricsRecorder


SinkMode = Literal["tty", "json", "quiet"]


class StructlogSink:
    """Adapter mapping :class:`DomainEvent`s onto a configured structlog logger.

    Parameters
    ----------
    mode:
        ``"tty"``    — :class:`structlog.dev.ConsoleRenderer` (Rich-coloured).
        ``"json"``   — :class:`structlog.processors.JSONRenderer`.
        ``"quiet"``  — every event is dropped on the floor.
    redactor:
        Defaults to ``SecretRedactor(RedactionPolicy.default())`` so
        that *every* construction has secret hygiene without the caller
        having to remember to wire it.
    metrics:
        Optional :class:`MetricsRecorder`. When set, ``emit`` calls
        ``metrics.from_event(event)`` purely for the side-effect of
        producing :class:`MetricRecord`s — subscribers consuming those
        records is out of scope for this sink.

    Notes
    -----
    Configuring structlog is process-global. We re-call
    :func:`structlog.configure` on every construction so the most-recent
    sink wins; this matches the CLI lifecycle (one sink per process).
    """

    def __init__(
        self,
        mode: SinkMode = "tty",
        *,
        redactor: SecretRedactor | None = None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        if mode not in ("tty", "json", "quiet"):
            raise ValueError(
                f"StructlogSink mode must be one of 'tty', 'json', 'quiet'; got {mode!r}",
            )
        self._mode: SinkMode = mode
        self._redactor: SecretRedactor = redactor or SecretRedactor(
            RedactionPolicy.default(),
        )
        self._metrics: MetricsRecorder | None = metrics
        self._configure_structlog()
        self._logger = structlog.get_logger("ai_platform_generator.telemetry")

    # ------------------------------------------------------------------
    # TelemetrySink protocol
    # ------------------------------------------------------------------

    def emit(self, event: DomainEvent) -> None:
        if self._mode == "quiet":
            # Still allow the metrics side-effect — operators pipe
            # ``--quiet`` runs into Prometheus quite happily.
            if self._metrics is not None:
                self._metrics.from_event(event)
            return

        payload = self._build_payload(event)
        redacted = self._redactor.redact_mapping(payload)
        # ``event_id`` / ``run_id`` and friends end up as structlog
        # key=value pairs; the event ``name`` is the log message.
        self._logger.info(event.name, **redacted)

        if self._metrics is not None:
            self._metrics.from_event(event)

    def flush(self) -> None:
        # structlog itself doesn't buffer, but the underlying stream
        # might. Best effort — never raise from a sink.
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            sys.stderr.flush()
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            sys.stdout.flush()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(event: DomainEvent) -> dict[str, Any]:
        """Flatten the envelope into the kwargs structlog expects."""
        return {
            "event_id": str(event.event_id),
            "run_id": None if event.run_id is None else str(event.run_id),
            "context": event.context,
            "schema_version": event.schema_version,
            "occurred_at": event.occurred_at.isoformat(),
            # Nest the payload so secret-key matching in
            # :meth:`SecretRedactor.redact_mapping` only fires on the
            # event's *own* payload keys, not on envelope metadata.
            "payload": dict(event.payload),
        }

    def _configure_structlog(self) -> None:
        if self._mode == "json":
            renderer: Any = structlog.processors.JSONRenderer()
        else:  # tty
            renderer = structlog.dev.ConsoleRenderer(colors=False)

        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=False,
        )
