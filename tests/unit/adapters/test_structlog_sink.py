"""Tests for :class:`StructlogSink`."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
import structlog

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.telemetry.structlog_sink import StructlogSink
from ai_platform_generator.domain.events.envelope import DomainEvent
from ai_platform_generator.domain.observability.metrics import MetricsRecorder


def _event(name: str = "TestEvent", payload: dict[str, Any] | None = None) -> DomainEvent:
    return DomainEvent(
        event_id=uuid4(),
        run_id=None,
        name=name,
        schema_version=1,
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        context="orchestrator",
        payload=payload or {},
    )


def _capture(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Redirect structlog's stderr-bound logger into a capture buffer."""
    buf = io.StringIO()
    monkeypatch.setattr(
        "ai_platform_generator.adapters.telemetry.structlog_sink.sys.stderr",
        buf,
    )
    return buf


class TestModes:
    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            StructlogSink(mode="bogus")  # type: ignore[arg-type]

    def test_quiet_mode_drops_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        buf = _capture(monkeypatch)
        sink = StructlogSink(mode="quiet")
        sink.emit(_event())
        assert buf.getvalue() == ""

    def test_tty_mode_writes_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Re-bind structlog to a captured stream via PrintLoggerFactory.
        buf = io.StringIO()
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
            logger_factory=structlog.PrintLoggerFactory(file=buf),
            cache_logger_on_first_use=False,
        )
        # Now build the sink — it will reconfigure to its own stream
        # (sys.stderr) which we monkeypatch:
        buf2 = _capture(monkeypatch)
        sink = StructlogSink(mode="tty")
        sink.emit(_event(name="MyEvent"))
        out = buf2.getvalue()
        assert "MyEvent" in out

    def test_json_mode_emits_one_json_per_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        buf = _capture(monkeypatch)
        sink = StructlogSink(mode="json")
        sink.emit(_event(name="JsonEvent", payload={"msg": "hello"}))
        line = buf.getvalue().strip()
        assert line, f"no output captured; buffer={buf.getvalue()!r}"
        record = json.loads(line)
        assert record["event"] == "JsonEvent"
        assert record["payload"] == {"msg": "hello"}


class TestRedaction:
    def test_redacts_secret_keys_in_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        buf = _capture(monkeypatch)
        sink = StructlogSink(mode="json")
        sink.emit(_event(payload={"api_key": "sk-EXAMPLE"}))
        record = json.loads(buf.getvalue().strip())
        assert record["payload"]["api_key"] == "[REDACTED]"

    def test_redacts_pattern_in_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        buf = _capture(monkeypatch)
        sink = StructlogSink(mode="json")
        sink.emit(_event(payload={"note": "Bearer abc.def-ghi"}))
        record = json.loads(buf.getvalue().strip())
        assert record["payload"]["note"] == "[REDACTED]"


class TestMetrics:
    def test_metrics_recorder_invoked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _capture(monkeypatch)
        seen: list[Any] = []

        class FakeRecorder(MetricsRecorder):
            def from_event(self, event: DomainEvent) -> tuple[Any, ...]:  # type: ignore[override]
                seen.append(event)
                return ()

        sink = StructlogSink(
            mode="quiet",
            metrics=FakeRecorder(FrozenClock()),
        )
        ev = _event(name="RunSucceeded")
        sink.emit(ev)
        # Even in quiet mode, metrics fire so dashboards still work.
        assert seen == [ev]

    def test_metrics_optional(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _capture(monkeypatch)
        sink = StructlogSink(mode="quiet")
        sink.emit(_event())  # must not raise.


class TestFlush:
    def test_flush_calls_stream_flush(self, monkeypatch: pytest.MonkeyPatch) -> None:
        flushed: list[str] = []

        class _Tracker(io.StringIO):
            def __init__(self, name: str) -> None:
                super().__init__()
                self._name = name

            def flush(self) -> None:  # type: ignore[override]
                flushed.append(self._name)

        monkeypatch.setattr(
            "ai_platform_generator.adapters.telemetry.structlog_sink.sys.stderr",
            _Tracker("stderr"),
        )
        monkeypatch.setattr(
            "ai_platform_generator.adapters.telemetry.structlog_sink.sys.stdout",
            _Tracker("stdout"),
        )
        sink = StructlogSink(mode="json")
        sink.flush()
        assert "stderr" in flushed and "stdout" in flushed
