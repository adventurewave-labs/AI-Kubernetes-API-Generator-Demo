"""Tests for :class:`DemoModeLlmAdapter`.

The adapter implements the :class:`LlmProvider` contract — every
response must be in the *legacy intent shape* consumed by
:class:`IntentInterpretationService._build_request`:

* top-level ``group`` / ``version`` / ``kind`` strings,
* ``spec_properties`` as an object keyed by camelCase property name,
* ``output_dir`` (relative path string),
* ``description`` (string).

The catalogue itself persists payloads in the modern
``CodegenRequest.to_dict()`` shape (nested ``gvk``,
``spec_properties`` as a list); the adapter translates on the fly.
"""

from __future__ import annotations

import re

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import (
    DemoCatalog,
    DemoScenario,
)
from ai_platform_generator.adapters.llm.demo_mode import DemoModeLlmAdapter
from ai_platform_generator.domain.values import ProviderMode
from ai_platform_generator.ports import LlmProvider

# Reverse-DNS-ish: at least one dot, all lowercase / digits / hyphens.
_REVERSE_DNS_RE = re.compile(r"^[a-z0-9.-]+\.[a-z0-9.-]+$")

# The six top-level keys the LLM-intent contract requires.
_REQUIRED_KEYS = {
    "group",
    "version",
    "kind",
    "spec_properties",
    "output_dir",
    "description",
}


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


def test_complete_json_returns_legacy_intent_payload_for_postgres() -> None:
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("system", "I want a postgres cluster")
    assert payload["kind"] == "PostgresCluster"
    assert payload["group"] == "database.cnoe.io"
    assert "spec_properties" in payload
    assert isinstance(payload["spec_properties"], dict)


def test_complete_json_returns_fallback_for_unmatched_query() -> None:
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("system", "completely unrelated query")
    # The default fallback is the ``vector-db`` scenario.
    assert payload["kind"] == "VectorDB"
    assert payload["group"] == "ai.platform.cnoe.io"


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


def test_custom_catalog_legacy_shape_passes_through() -> None:
    """A custom catalogue authored in the legacy intent shape passes through verbatim."""
    custom = DemoCatalog(
        scenarios=[
            DemoScenario(
                name="vector-db",
                keywords=("vector",),
                request={
                    "group": "g.example.com",
                    "version": "v1",
                    "kind": "VectorDB",
                    "spec_properties": {"dim": {"type": "integer"}},
                    "output_dir": "out",
                    "description": "x",
                },
            ),
            DemoScenario(
                name="alt",
                keywords=("foobar",),
                request={
                    "group": "alt.example.com",
                    "version": "v1",
                    "kind": "Alt",
                    "spec_properties": {"v": {"type": "string"}},
                    "output_dir": "out",
                    "description": "alt",
                },
            ),
        ],
    )
    adapter = DemoModeLlmAdapter(catalog=custom)
    assert adapter.complete_json("s", "say foobar")["kind"] == "Alt"
    # And the fallback is the catalogue's vector-db.
    assert adapter.complete_json("s", "nothing here")["kind"] == "VectorDB"


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


# ---------------------------------------------------------------------------
# Wave 8 regression tests — Issue: ``LLM response missing required GVK key``
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_name",
    [s.name for s in DemoCatalog().scenarios],
)
def test_demo_mode_response_always_includes_group(scenario_name: str) -> None:
    """Every catalogue scenario emits a response with a valid reverse-DNS ``group``.

    Regression test for the Wave 8 chunk (1) bug where
    :class:`DemoModeLlmAdapter` returned the modern
    ``CodegenRequest.to_dict()`` shape (nested ``gvk``), causing
    :meth:`IntentInterpretationService._build_request` to raise
    ``DomainValidationError("LLM response missing required GVK key: 'group'")``.
    """
    catalog = DemoCatalog()
    scenario = catalog.by_name(scenario_name)
    adapter = DemoModeLlmAdapter(catalog=catalog)
    # Use the first keyword as a deterministic trigger for this scenario.
    payload = adapter.complete_json("", scenario.keywords[0])

    assert _REQUIRED_KEYS.issubset(payload.keys()), (
        f"scenario {scenario_name!r} payload missing keys: "
        f"{_REQUIRED_KEYS - set(payload.keys())}"
    )
    assert "group" in payload
    assert isinstance(payload["group"], str) and payload["group"]
    assert _REVERSE_DNS_RE.match(payload["group"]), (
        f"scenario {scenario_name!r} group {payload['group']!r} "
        f"is not reverse-DNS"
    )


def test_demo_mode_unknown_intent_returns_valid_default() -> None:
    """A query that matches no keyword still yields a valid response.

    The catalogue's fallback (``vector-db``) provides ``group``,
    ``version``, ``kind``, ``spec_properties``, ``output_dir`` and
    ``description``. The fallback's group must satisfy reverse-DNS.
    """
    adapter = DemoModeLlmAdapter()
    payload = adapter.complete_json("", "xyzzy quux nothing matches")

    # All six required keys present.
    assert _REQUIRED_KEYS.issubset(payload.keys())
    # Default fallback is vector-db; its group is the ai.platform.cnoe.io
    # reverse-DNS that ADR-0009 §10 mandates.
    assert payload["group"] == "ai.platform.cnoe.io"
    assert _REVERSE_DNS_RE.match(payload["group"])
    # ``spec_properties`` must be non-empty so downstream codegen has
    # something to materialise.
    assert payload["spec_properties"]
    assert isinstance(payload["spec_properties"], dict)


def test_demo_mode_response_parses_into_codegen_request() -> None:
    """End-to-end: the adapter's output flows through ``IntentInterpretationService.parse``.

    This is the test that would have caught the original bug — feeding
    every demo scenario through the real
    :class:`IntentInterpretationService` and asserting the result is a
    valid :class:`CodegenRequest` without any
    :class:`DomainValidationError`.
    """
    from datetime import datetime, timezone

    from ai_platform_generator.adapters.clock.frozen import FrozenClock
    from ai_platform_generator.adapters.telemetry.recording import RecordingSink
    from ai_platform_generator.application.services.intent_interpretation import (
        IntentInterpretationService,
    )
    from ai_platform_generator.domain.values import Intent

    catalog = DemoCatalog()
    for scenario in catalog.scenarios:
        adapter = DemoModeLlmAdapter(catalog=catalog)
        service = IntentInterpretationService(
            llm=adapter,
            validator=None,
            enhancer=None,
            events=RecordingSink(),
            clock=FrozenClock(
                initial=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )
        intent = Intent(
            text=scenario.keywords[0],
            submitted_at=datetime(
                2026, 5, 11, 11, 59, 0, tzinfo=timezone.utc,
            ),
        )
        request = service.parse(intent)
        # The parsed request must declare the scenario's GVK.
        scenario_gvk = scenario.request["gvk"]
        assert request.gvk.group.value == scenario_gvk["group"], (
            f"scenario {scenario.name!r}: group mismatch"
        )
        assert request.gvk.kind.value == scenario_gvk["kind"], (
            f"scenario {scenario.name!r}: kind mismatch"
        )
        assert request.provider_mode is ProviderMode.DEMO
        # And spec_properties round-tripped without loss.
        assert len(request.spec_properties) == len(
            scenario.request["spec_properties"]
        )
