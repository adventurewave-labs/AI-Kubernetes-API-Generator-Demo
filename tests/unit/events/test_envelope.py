"""Tests for :class:`DomainEvent` (the envelope).

Pins immutability, the ``to_dict`` shape, and JSON-serialisability of the
default payload conventions.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from ai_platform_generator.domain.events import VALID_CONTEXTS, DomainEvent


def _sample(**overrides: object) -> DomainEvent:
    base = dict(
        event_id=uuid4(),
        run_id=None,
        name="IntentSubmitted",
        schema_version=1,
        occurred_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        context="intent",
        payload={"intent_text_hash": "abc", "intent_length": 42},
        causation_id=None,
    )
    base.update(overrides)
    return DomainEvent(**base)  # type: ignore[arg-type]


def test_envelope_is_frozen() -> None:
    e = _sample()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.name = "Other"  # type: ignore[misc]


def test_to_dict_shape() -> None:
    e = _sample()
    d = e.to_dict()
    assert set(d.keys()) == {
        "event_id",
        "run_id",
        "name",
        "schema_version",
        "occurred_at",
        "context",
        "payload",
        "causation_id",
    }
    # Stringified UUID, ISO-8601 timestamp.
    UUID(d["event_id"])  # parses
    assert d["occurred_at"] == "2026-05-10T12:00:00+00:00"
    assert d["payload"] == {"intent_text_hash": "abc", "intent_length": 42}


def test_to_dict_is_json_serialisable() -> None:
    e = _sample(causation_id=uuid4())
    blob = json.dumps(e.to_dict())
    parsed = json.loads(blob)
    assert parsed["name"] == "IntentSubmitted"
    assert parsed["context"] == "intent"


def test_to_dict_handles_none_run_id_and_causation_id() -> None:
    e = _sample()
    d = e.to_dict()
    assert d["run_id"] is None
    assert d["causation_id"] is None


def test_payload_view_is_decoupled_from_dict() -> None:
    payload = {"a": 1}
    e = _sample(payload=payload)
    d = e.to_dict()
    d["payload"]["a"] = 999
    # Mutating the dict copy must not corrupt the envelope's payload.
    assert e.payload["a"] == 1


def test_valid_contexts_constants() -> None:
    expected = {
        "intent",
        "modelling",
        "generation",
        "cluster",
        "user_interaction",
        "orchestrator",
    }
    assert VALID_CONTEXTS == expected
