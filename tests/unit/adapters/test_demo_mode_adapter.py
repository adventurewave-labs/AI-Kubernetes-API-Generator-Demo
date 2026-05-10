"""Tests for :class:`DemoModeLlmAdapter`."""

from __future__ import annotations

from ai_platform_generator.adapters.llm.demo_catalog import (
    DemoCatalog,
    DemoScenario,
)
from ai_platform_generator.adapters.llm.demo_mode import DemoModeLlmAdapter
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.values import ProviderMode
from ai_platform_generator.ports import LlmProvider


def test_adapter_satisfies_llm_provider_protocol() -> None:
    adapter = DemoModeLlmAdapter()
    assert isinstance(adapter, LlmProvider)


def test_adapter_is_always_available() -> None:
    adapter = DemoModeLlmAdapter()
    assert adapter.is_available() is True
    # Repeated calls remain True.
    assert adapter.is_available() is True


def test_adapter_mode_is_demo() -> None:
    adapter = DemoModeLlmAdapter()
    assert adapter.mode is ProviderMode.DEMO


def test_complete_json_returns_valid_codegen_request_payload() -> None:
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("system", "I want a postgres cluster")
    # The payload must round-trip into a CodegenRequest.
    request = CodegenRequest.from_dict(payload)
    assert request.gvk.kind.value == "PostgresCluster"
    assert request.provider_mode is ProviderMode.DEMO


def test_complete_json_returns_fallback_for_unmatched_query() -> None:
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("system", "completely unrelated query")
    request = CodegenRequest.from_dict(payload)
    assert request.gvk.kind.value == "VectorDB"


def test_complete_json_records_last_scenario() -> None:
    adapter = DemoModeLlmAdapter()
    adapter.complete_json("s", "I need redis for caching")
    assert adapter.last_scenario_name == "redis-cluster"


def test_complete_json_returns_independent_copy() -> None:
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("s", "postgres")
    payload["mutated"] = True  # type: ignore[index]
    # Re-fetching from the catalogue must not have the mutation.
    again = adapter.complete_json("s", "postgres")
    assert "mutated" not in again


def test_custom_catalog_is_honoured() -> None:
    custom = DemoCatalog(
        scenarios=[
            DemoScenario(
                name="vector-db",
                keywords=("vector",),
                request={"hello": "world"},
            ),
            DemoScenario(
                name="alt",
                keywords=("foobar",),
                request={"alt": True},
            ),
        ],
    )
    adapter = DemoModeLlmAdapter(catalog=custom)
    assert adapter.complete_json("s", "say foobar") == {"alt": True}
    # And the fallback is the catalogue's vector-db.
    assert adapter.complete_json("s", "nothing here") == {"hello": "world"}


def test_complete_json_accepts_optional_kwargs() -> None:
    adapter = DemoModeLlmAdapter()
    # json_schema and timeout_s are accepted but ignored — must not raise.
    out = adapter.complete_json(
        "s",
        "postgres",
        json_schema={"type": "object"},
        timeout_s=12.5,
    )
    assert isinstance(out, dict)
