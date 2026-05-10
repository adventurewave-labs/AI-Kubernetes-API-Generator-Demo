"""Unit tests for :class:`JsonRenderer` (NDJSON output)."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from enum import Enum
from io import StringIO
from pathlib import Path
from uuid import UUID

from ai_platform_generator.adapters.cli.exit_codes import (
    EXIT_DOMAIN_VALIDATION,
)
from ai_platform_generator.adapters.cli.rendering._json_default import (
    _json_default,
)
from ai_platform_generator.adapters.cli.rendering.json_renderer import (
    JsonRenderer,
)
from ai_platform_generator.application.orchestrator import GenerationSummary
from ai_platform_generator.domain.errors import EmptySpec
from ai_platform_generator.domain.events import (
    ArtifactGenerated,
    DemoModeEngaged,
    RunStarted,
    RunSucceeded,
    StageStarted,
    StageSucceeded,
)


def _read_lines(buffer: StringIO) -> list[dict]:
    raw = buffer.getvalue().splitlines()
    return [json.loads(line) for line in raw]


def test_begin_writes_command_started_line() -> None:
    buf = StringIO()
    renderer = JsonRenderer(stream=buf)
    renderer.begin()
    lines = _read_lines(buf)
    assert len(lines) == 1
    assert lines[0]["type"] == "command_started"
    assert "ts" in lines[0]
    assert "tool_version" in lines[0]


def test_each_event_is_one_valid_json_line() -> None:
    buf = StringIO()
    renderer = JsonRenderer(stream=buf)
    events = [
        RunStarted.make(run_id=None, payload={}),
        StageStarted.make(run_id=None, payload={"stage": "interpret"}),
        StageSucceeded.make(
            run_id=None, payload={"stage": "interpret", "elapsed_ms": 5}
        ),
        ArtifactGenerated.make(
            run_id=None,
            payload={"artifact_type": "crd", "path": "/tmp/widget-crd.yaml"},
        ),
        DemoModeEngaged.make(
            run_id=None, payload={"reason": "E_INTENT_LLM_UNAVAILABLE"}
        ),
        RunSucceeded.make(run_id=None, payload={}),
    ]
    for event in events:
        renderer.event(event)

    lines = _read_lines(buf)
    assert len(lines) == len(events)
    for line, event in zip(lines, events, strict=True):
        assert line["type"] == "domain_event"
        assert line["name"] == event.name
        assert "payload" in line
        assert line["context"] == event.context
        assert line["schema_version"] == event.schema_version


def test_end_emits_summary_line() -> None:
    buf = StringIO()
    renderer = JsonRenderer(stream=buf)
    summary = GenerationSummary(
        run_id="11111111-1111-1111-1111-111111111111",
        state="succeeded",
        gvk="example.io/v1/Widget",
        bundle_dir=Path("/tmp/out"),
        artefact_paths=[Path("/tmp/out/widget-crd.yaml")],
        cluster_name="kind-test",
        deployment_status="ready",
        duration_ms=987,
        provider_mode="live",
    )
    renderer.end(summary)
    lines = _read_lines(buf)
    assert len(lines) == 1
    line = lines[0]
    assert line["type"] == "summary"
    assert line["state"] == "succeeded"
    assert line["bundle_dir"] == "/tmp/out"
    assert line["artefact_paths"] == ["/tmp/out/widget-crd.yaml"]
    assert line["duration_ms"] == 987


def test_error_emits_error_line_and_returns_exit_code() -> None:
    buf = StringIO()
    renderer = JsonRenderer(stream=buf)
    err = EmptySpec(
        remediation_hint="Add at least one field",
        violation_count=1,
    )
    code = renderer.error(err)
    lines = _read_lines(buf)
    assert code == EXIT_DOMAIN_VALIDATION
    assert len(lines) == 1
    line = lines[0]
    assert line["type"] == "error"
    assert line["code"] == err.code
    assert line["user_message"] == err.user_message
    assert line["extras"]["remediation_hint"] == "Add at least one field"
    assert line["extras"]["violation_count"] == 1


def test_lines_are_flushed_after_each_write() -> None:
    class _Recorder(StringIO):
        flushes: int = 0

        def flush(self) -> None:  # type: ignore[override]
            self.flushes += 1
            super().flush()

    buf = _Recorder()
    renderer = JsonRenderer(stream=buf)
    renderer.begin()
    renderer.event(RunStarted.make(run_id=None, payload={}))
    assert buf.flushes >= 2


# ---------------------------------------------------------------------------
# _json_default coverage
# ---------------------------------------------------------------------------


class _Color(Enum):
    RED = "red"
    BLUE = "blue"


def test_json_default_handles_path_uuid_datetime_enum_bytes() -> None:
    payload = {
        "path": Path("/tmp/x"),
        "uuid": UUID("11111111-1111-1111-1111-111111111111"),
        "ts": datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        "color": _Color.RED,
        "blob": b"hello",
    }
    encoded = json.dumps(payload, default=_json_default)
    decoded = json.loads(encoded)
    assert decoded["path"] == "/tmp/x"
    assert decoded["uuid"] == "11111111-1111-1111-1111-111111111111"
    assert decoded["ts"].endswith("Z")
    assert decoded["color"] == "red"
    assert decoded["blob"] == base64.b64encode(b"hello").decode("ascii")


def test_json_default_falls_back_to_marker_for_unknown_types() -> None:
    class Foo:
        pass

    encoded = json.dumps({"x": Foo()}, default=_json_default)
    decoded = json.loads(encoded)
    assert decoded["x"]["_unserialisable"] is True
    assert "Foo" in decoded["x"]["repr"]
