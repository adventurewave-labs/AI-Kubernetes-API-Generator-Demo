"""Shared fixtures for the application-services unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.domain.values import Intent


@pytest.fixture
def sink() -> RecordingSink:
    return RecordingSink()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(initial=datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def intent() -> Intent:
    return Intent(
        text="I want a Postgres cluster with 3 replicas and 10Gi storage.",
        submitted_at=datetime(2026, 5, 10, 11, 59, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def llm_response_postgres() -> dict[str, object]:
    """Canned LLM JSON for the postgres-cluster scenario."""
    return {
        "group": "platform.example.com",
        "version": "v1alpha1",
        "kind": "PostgresCluster",
        "spec_properties": {
            "replicas": {"type": "integer", "minimum": 1, "maximum": 7},
            "storageSize": "string",
            "version": {"type": "string", "description": "Postgres version"},
        },
        "output_dir": "generated_specs/postgrescluster",
        "description": "A managed Postgres cluster with replicas.",
    }
