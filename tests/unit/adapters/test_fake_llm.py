"""Tests for :class:`FakeLlmAdapter`."""

from __future__ import annotations

import pytest

from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter


def test_enqueue_and_dequeue_in_order() -> None:
    adapter = FakeLlmAdapter()
    adapter.enqueue({"first": 1})
    adapter.enqueue({"second": 2})

    assert adapter.is_available() is True
    assert adapter.complete_json("sys", "user") == {"first": 1}
    assert adapter.complete_json("sys", "user") == {"second": 2}
    assert adapter.is_available() is False


def test_initial_responses_constructor_arg() -> None:
    adapter = FakeLlmAdapter(responses=[{"a": 1}, {"b": 2}])
    assert adapter.is_available() is True
    assert adapter.complete_json("s", "u") == {"a": 1}
    assert adapter.complete_json("s", "u") == {"b": 2}
    # Queue exhausted.
    assert adapter.is_available() is False


def test_complete_json_records_call_metadata() -> None:
    adapter = FakeLlmAdapter(responses=[{"x": 1}])
    schema = {"type": "object"}
    adapter.complete_json("system", "user", json_schema=schema, timeout_s=30.0)

    assert adapter.calls == [("system", "user", schema, 30.0)]


def test_exhaustion_raises_runtime_error() -> None:
    adapter = FakeLlmAdapter()

    with pytest.raises(RuntimeError, match="no canned response"):
        adapter.complete_json("s", "u")


def test_name_and_model_constants() -> None:
    adapter = FakeLlmAdapter()
    assert adapter.name == "fake"
    assert adapter.model == "fake-1"


def test_remaining_property() -> None:
    adapter = FakeLlmAdapter(responses=[{"a": 1}, {"b": 2}])
    assert adapter.remaining == 2
    adapter.complete_json("s", "u")
    assert adapter.remaining == 1
