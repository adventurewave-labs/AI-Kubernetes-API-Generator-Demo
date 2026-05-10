"""Telemetry / logging / tracing adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.telemetry.multi import MultiSink
from ai_platform_generator.adapters.telemetry.noop import NoopSink
from ai_platform_generator.adapters.telemetry.otel_sink import OtelSink
from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.adapters.telemetry.structlog_sink import StructlogSink

__version__ = "0.1.0"

__all__ = [
    "MultiSink",
    "NoopSink",
    "OtelSink",
    "RecordingSink",
    "StructlogSink",
    "__version__",
]
