"""Catalogue completeness tests (docs/ddd/05-domain-events.md §3).

Asserts that:

* every concrete event subclass declares ``NAME`` and ``SCHEMA_VERSION``;
* every subclass binds itself to a valid producing context;
* ``make(...)`` returns a fully-populated :class:`DomainEvent`;
* the catalogue contains exactly the 35 events the doc enumerates;
* ``NAME`` values are unique;
* per-context groupings match the spec (counts).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from ai_platform_generator.domain.events import (
    ALL_EVENT_TYPES,
    VALID_CONTEXTS,
    DomainEvent,
)

# Spec-derived expectation: every event in §3 of the design doc.
EXPECTED_NAMES_BY_CONTEXT: dict[str, set[str]] = {
    "intent": {
        "IntentSubmitted",
        "LlmInvocationStarted",
        "LlmInvocationSucceeded",
        "LlmInvocationFailed",
        "DemoModeEngaged",
        "CodegenRequestParsed",
        "CodegenRequestRejected",
    },
    "modelling": {"IRConstructed", "IRRejected"},
    "generation": {
        "GenerationPlanned",
        "ArtifactRendered",
        "ArtifactPostProcessed",
        "ArtifactGenerated",
        "ArtifactBundleSealed",
        "ArtifactGenerationFailed",
    },
    "cluster": {
        "PrerequisiteCheckSucceeded",
        "PrerequisiteCheckFailed",
        "ClusterCreationStarted",
        "ClusterCreationSucceeded",
        "ClusterCreationFailed",
        "CrdApplied",
        "InstanceApplied",
        "DeploymentVerified",
        "DeploymentVerificationFailed",
    },
    "user_interaction": {
        "CommandStarted",
        "CommandSucceeded",
        "CommandFailed",
        "RenderModeChosen",
    },
    "orchestrator": {
        "RunStarted",
        "StageStarted",
        "StageSucceeded",
        "StageFailed",
        "CompensationApplied",
        "RunSucceeded",
        "RunFailed",
    },
}

EXPECTED_TOTAL = sum(len(v) for v in EXPECTED_NAMES_BY_CONTEXT.values())
assert EXPECTED_TOTAL == 35, "spec sanity: §3 enumerates 35 events"


def test_catalog_has_exactly_thirty_five_events() -> None:
    assert len(ALL_EVENT_TYPES) == 35


def test_catalog_names_are_unique() -> None:
    names = [t.NAME for t in ALL_EVENT_TYPES]
    assert len(names) == len(set(names)), "duplicate NAME in catalogue"


def test_catalog_matches_doc_per_context() -> None:
    by_ctx: dict[str, set[str]] = {}
    for cls in ALL_EVENT_TYPES:
        by_ctx.setdefault(cls.CONTEXT, set()).add(cls.NAME)
    assert by_ctx == EXPECTED_NAMES_BY_CONTEXT


@pytest.mark.parametrize("cls", ALL_EVENT_TYPES, ids=lambda c: c.__name__)
def test_each_event_class_metadata(cls: type) -> None:
    assert isinstance(cls.NAME, str) and cls.NAME, f"{cls.__name__}.NAME"
    assert cls.NAME == cls.__name__, (
        f"NAME and class name should match for wire stability: {cls!r}"
    )
    assert isinstance(cls.SCHEMA_VERSION, int) and cls.SCHEMA_VERSION >= 1
    assert cls.CONTEXT in VALID_CONTEXTS, (
        f"{cls.__name__}.CONTEXT={cls.CONTEXT!r} not in {VALID_CONTEXTS}"
    )


@pytest.mark.parametrize("cls", ALL_EVENT_TYPES, ids=lambda c: c.__name__)
def test_make_produces_valid_envelope(cls: type) -> None:
    before = datetime.now(timezone.utc)
    event = cls.make(run_id=None, payload={"k": "v"})
    after = datetime.now(timezone.utc)

    assert isinstance(event, DomainEvent)
    assert isinstance(event, cls)
    assert event.name == cls.NAME
    assert event.context == cls.CONTEXT
    assert event.schema_version == cls.SCHEMA_VERSION
    assert event.payload == {"k": "v"}
    assert event.run_id is None
    assert event.causation_id is None
    assert isinstance(event.event_id, UUID)
    assert before <= event.occurred_at <= after


def test_make_propagates_causation_id() -> None:
    cause = UUID("11111111-1111-1111-1111-111111111111")
    e = ALL_EVENT_TYPES[0].make(run_id=None, payload={}, causation_id=cause)
    assert e.causation_id == cause


def test_make_payload_is_copied() -> None:
    payload = {"a": 1}
    e = ALL_EVENT_TYPES[0].make(run_id=None, payload=payload)
    payload["a"] = 999
    assert e.payload["a"] == 1


def test_make_emits_distinct_event_ids() -> None:
    cls = ALL_EVENT_TYPES[0]
    ids = {cls.make(run_id=None, payload={}).event_id for _ in range(50)}
    assert len(ids) == 50
