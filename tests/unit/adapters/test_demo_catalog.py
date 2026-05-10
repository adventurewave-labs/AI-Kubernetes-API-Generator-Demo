"""Tests for the built-in :class:`DemoCatalog` and :class:`DemoScenario`."""

from __future__ import annotations

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import (
    DemoCatalog,
    DemoScenario,
)
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest


def test_default_catalog_has_all_eight_scenarios() -> None:
    catalog = DemoCatalog()
    names = [s.name for s in catalog.scenarios]
    assert names == [
        "postgres-cluster",
        "redis-cluster",
        "vector-db",
        "notebook",
        "database-backup",
        "cache-cluster",
        "monitoring-service",
        "ml-pipeline",
    ]


def test_every_scenario_round_trips_through_codegen_request() -> None:
    catalog = DemoCatalog()
    for scenario in catalog.scenarios:
        request = CodegenRequest.from_dict(scenario.request)
        # Re-serialise and re-parse to ensure stability.
        round_tripped = CodegenRequest.from_dict(request.to_dict())
        assert round_tripped == request, (
            f"scenario {scenario.name} did not round-trip cleanly"
        )


@pytest.mark.parametrize(
    "query, expected",
    [
        ("I want a postgres cluster", "postgres-cluster"),
        ("postgresql, please", "postgres-cluster"),
        ("redis cache for sessions", "redis-cluster"),
        ("vector embeddings store", "vector-db"),
        ("Jupyter notebook with GPU", "notebook"),
        ("Schedule a backup of my database", "database-backup"),
        ("CacheCluster for the app", "cache-cluster"),
        ("monitoring service please", "monitoring-service"),
        ("ML pipeline with stages", "ml-pipeline"),
    ],
)
def test_find_keyword_matching(query: str, expected: str) -> None:
    catalog = DemoCatalog()
    assert catalog.find(query).name == expected


def test_find_is_case_insensitive() -> None:
    catalog = DemoCatalog()
    assert catalog.find("POSTGRES").name == "postgres-cluster"
    assert catalog.find("PoStGrEs").name == "postgres-cluster"


def test_find_falls_back_to_vector_db_when_nothing_matches() -> None:
    catalog = DemoCatalog()
    assert catalog.find("xyzzy quux").name == "vector-db"
    assert catalog.find("").name == "vector-db"


def test_find_returns_first_matching_scenario_in_order() -> None:
    # "backup" matches database-backup; the query also mentions "redis"
    # earlier — we want the *first* keyword in catalogue order to win.
    catalog = DemoCatalog()
    # postgres-cluster comes first; if its keyword is in the query, it wins
    # over redis-cluster keywords appearing later in the same string.
    assert catalog.find("postgres or redis?").name == "postgres-cluster"


def test_demo_scenario_is_frozen() -> None:
    scenario = DemoScenario(
        name="x",
        keywords=("k",),
        request={"foo": "bar"},
    )
    with pytest.raises(Exception):  # pydantic frozen → ValidationError
        scenario.name = "y"  # type: ignore[misc]


def test_catalog_rejects_empty_scenarios() -> None:
    with pytest.raises(ValueError, match="at least one scenario"):
        DemoCatalog(scenarios=[])


def test_catalog_rejects_duplicate_names() -> None:
    s1 = DemoScenario(name="a", keywords=("a",), request={})
    s2 = DemoScenario(name="a", keywords=("b",), request={})
    with pytest.raises(ValueError, match="unique"):
        DemoCatalog(scenarios=[s1, s2])


def test_catalog_rejects_unknown_fallback() -> None:
    s = DemoScenario(name="only", keywords=("x",), request={})
    with pytest.raises(ValueError, match="fallback"):
        DemoCatalog(scenarios=[s], fallback_name="nope")


def test_catalog_by_name_lookup() -> None:
    catalog = DemoCatalog()
    assert catalog.by_name("notebook").name == "notebook"
    with pytest.raises(KeyError):
        catalog.by_name("not-a-real-scenario")


def test_default_fallback_is_vector_db() -> None:
    catalog = DemoCatalog()
    assert catalog.fallback.name == "vector-db"
