"""Telemetry / logging / tracing adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.telemetry.multi import MultiSink
from ai_platform_generator.adapters.telemetry.noop import NoopSink
from ai_platform_generator.adapters.telemetry.recording import RecordingSink

__version__ = "0.1.0"

__all__ = ["MultiSink", "NoopSink", "RecordingSink", "__version__"]
