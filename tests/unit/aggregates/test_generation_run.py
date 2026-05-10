"""Tests for ``GenerationRun`` entity and its state machine."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_platform_generator.domain.aggregates.generation_run import (
    Deployment,
    GenerationRun,
    IllegalRunTransition,
    InvalidGenerationRun,
    RunState,
)
from ai_platform_generator.domain.values import Intent, RunId


def _intent() -> Intent:
    return Intent(
        text="give me a database",
        submitted_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )


def _run() -> GenerationRun:
    return GenerationRun(
        id=RunId.new(),
        started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        intent=_intent(),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_run_starts_pending() -> None:
    r = _run()
    assert r.state is RunState.PENDING
    assert r.request is None
    assert r.ir is None
    assert r.bundle is None
    assert r.deployment is None


def test_run_requires_runid() -> None:
    with pytest.raises(InvalidGenerationRun):
        GenerationRun(
            id="not-a-runid",  # type: ignore[arg-type]
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            intent=_intent(),
        )


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


def test_normal_pipeline_succeeds() -> None:
    r = _run()
    r.transition_to(RunState.INTERPRETING)
    r.transition_to(RunState.MODELLING)
    r.transition_to(RunState.GENERATING)
    r.transition_to(RunState.PERSISTING)
    r.transition_to(RunState.SUCCEEDED)
    assert r.state is RunState.SUCCEEDED


def test_cluster_path_succeeds() -> None:
    r = _run()
    r.transition_to(RunState.INTERPRETING)
    r.transition_to(RunState.MODELLING)
    r.transition_to(RunState.GENERATING)
    r.transition_to(RunState.PERSISTING)
    r.transition_to(RunState.PROVISIONING)
    r.transition_to(RunState.VERIFYING)
    r.transition_to(RunState.SUCCEEDED)
    assert r.state is RunState.SUCCEEDED


def test_any_state_can_fail() -> None:
    for from_state in (
        RunState.INTERPRETING,
        RunState.MODELLING,
        RunState.GENERATING,
        RunState.PERSISTING,
        RunState.PROVISIONING,
        RunState.VERIFYING,
    ):
        r = _run()
        # Step into from_state.
        r.transition_to(RunState.INTERPRETING)
        if from_state is not RunState.INTERPRETING:
            r.transition_to(RunState.MODELLING)
        post_modelling_states = (
            RunState.GENERATING,
            RunState.PERSISTING,
            RunState.PROVISIONING,
            RunState.VERIFYING,
        )
        if from_state in post_modelling_states:
            r.transition_to(RunState.GENERATING)
        if from_state in (
            RunState.PERSISTING,
            RunState.PROVISIONING,
            RunState.VERIFYING,
        ):
            r.transition_to(RunState.PERSISTING)
        if from_state in (RunState.PROVISIONING, RunState.VERIFYING):
            r.transition_to(RunState.PROVISIONING)
        if from_state is RunState.VERIFYING:
            r.transition_to(RunState.VERIFYING)
        assert r.state is from_state
        r.transition_to(RunState.FAILED)
        assert r.state is RunState.FAILED


def test_illegal_transition_rejected() -> None:
    r = _run()
    with pytest.raises(IllegalRunTransition):
        r.transition_to(RunState.SUCCEEDED)  # PENDING -> SUCCEEDED illegal


def test_terminal_state_cannot_transition() -> None:
    r = _run()
    r.transition_to(RunState.INTERPRETING)
    r.transition_to(RunState.FAILED)
    with pytest.raises(IllegalRunTransition):
        r.transition_to(RunState.MODELLING)


def test_transition_requires_runstate_type() -> None:
    r = _run()
    with pytest.raises(ValueError):
        r.transition_to("interpreting")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------------------


def test_attach_deployment() -> None:
    r = _run()
    dep = Deployment(id=uuid4(), cluster_name="kind-test")
    r.attach_deployment(dep)
    assert r.deployment is dep


def test_attach_deployment_rejects_wrong_type() -> None:
    r = _run()
    with pytest.raises(InvalidGenerationRun):
        r.attach_deployment("not a deployment")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_runs_compare_by_id() -> None:
    rid = RunId.new()
    a = GenerationRun(
        id=rid,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        intent=_intent(),
    )
    b = GenerationRun(
        id=rid,
        started_at=datetime(2026, 2, 2, tzinfo=timezone.utc),
        intent=_intent(),
    )
    assert a == b
    assert hash(a) == hash(b)


def test_runs_with_different_ids_are_unequal() -> None:
    a = _run()
    b = _run()
    assert a != b


# ---------------------------------------------------------------------------
# Deployment stub
# ---------------------------------------------------------------------------


def test_deployment_requires_uuid() -> None:
    with pytest.raises(InvalidGenerationRun):
        Deployment(id="not-uuid", cluster_name="x")  # type: ignore[arg-type]


def test_deployment_requires_non_blank_cluster() -> None:
    with pytest.raises(InvalidGenerationRun):
        Deployment(id=uuid4(), cluster_name="   ")
