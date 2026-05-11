"""Shared pytest configuration for the integration suite.

This module owns the *gates* that control which integration tests run
in a given environment:

* ``skip_without_openrouter`` — requires ``OPENROUTER_API_KEY``.
* ``skip_without_kind``      — requires both ``kind`` and ``docker``.
* ``skip_without_otel``      — requires the ``opentelemetry`` package.
* ``skip_without_network``   — requires DNS resolution for
  ``openrouter.ai``.

All four are cheap, side-effect-free fixtures: they call
:func:`pytest.skip` at fixture-setup time so collection still works in
restricted environments. Tests that need a writable directory use
:func:`tmp_artifact_root` which simply re-exports ``tmp_path``.

We also register the integration-specific markers so pytest's
``--strict-markers`` does not flag them.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import socket

import pytest


# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers used by the integration suite.

    Idempotent: pytest collapses duplicates with the project-wide
    ``markers`` list in ``pyproject.toml``.
    """
    for marker in (
        "integration: integration tests against real or simulated adapters",
        "requires_llm: integration tests requiring a live LLM API key",
        "requires_cluster: integration tests requiring kind + docker",
        "requires_otel: integration tests requiring the opentelemetry SDK",
        "requires_network: integration tests requiring outbound network access",
    ):
        config.addinivalue_line("markers", marker)


# ---------------------------------------------------------------------------
# Skip-gate fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def skip_without_openrouter() -> None:
    """Skip the test when ``OPENROUTER_API_KEY`` is missing.

    Yields ``None`` when the key is present so callers can reach for
    :func:`os.environ` themselves.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set; skipping live LLM test")


@pytest.fixture()
def skip_without_kind() -> None:
    """Skip the test unless ``kind`` and ``docker`` are both on PATH."""
    missing: list[str] = []
    if shutil.which("kind") is None:
        missing.append("kind")
    if shutil.which("docker") is None:
        missing.append("docker")
    if missing:
        pytest.skip(f"missing tools for cluster test: {', '.join(missing)}")


@pytest.fixture()
def skip_without_otel() -> None:
    """Skip the test unless the ``opentelemetry`` SDK is importable."""
    if importlib.util.find_spec("opentelemetry") is None:
        pytest.skip("opentelemetry-sdk not installed")
    # The OtelSink also needs the in-memory exporter — pinning it here
    # keeps the gate honest.
    if importlib.util.find_spec(
        "opentelemetry.sdk.trace.export.in_memory_span_exporter"
    ) is None:
        pytest.skip("opentelemetry in-memory span exporter not installed")


@pytest.fixture()
def skip_without_network() -> None:
    """Skip the test when DNS resolution to ``openrouter.ai`` fails.

    Uses :func:`socket.gethostbyname` directly so the gate is fast
    (sub-second on a healthy resolver) and does not depend on the
    ``httpx``/``openai`` stack being importable.
    """
    try:
        socket.gethostbyname("openrouter.ai")
    except OSError as exc:
        pytest.skip(f"network unavailable: {exc}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_artifact_root(tmp_path):  # type: ignore[no-untyped-def]
    """Return a fresh, writable directory for artefact-producing tests.

    A thin pass-through over ``tmp_path``, but exists as a named fixture
    so tests can ask for "the artefact root" rather than "a tmp dir".
    """
    return tmp_path


__all__ = [
    "skip_without_kind",
    "skip_without_network",
    "skip_without_openrouter",
    "skip_without_otel",
    "tmp_artifact_root",
]
