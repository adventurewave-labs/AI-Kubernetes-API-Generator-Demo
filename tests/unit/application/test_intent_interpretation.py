"""Unit tests for :class:`IntentInterpretationService`."""

from __future__ import annotations

from typing import Any

import pytest

from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
from ai_platform_generator.application.services.intent_interpretation import (
    IntentInterpretationService,
)
from ai_platform_generator.domain.errors import (
    DomainValidationError,
    FieldViolation,
    LlmRateLimited,
    LlmUnavailable,
)


class _RaisingLlm:
    """Tiny fake provider that yields a queued sequence of responses/raises."""

    name = "raising"
    model = "raising-1"
    mode = "live"

    def __init__(self, sequence: list[Any]) -> None:
        self._seq = list(sequence)
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Any = None,
        timeout_s: float = 60.0,
    ) -> dict[str, Any]:
        self.calls += 1
        item = self._seq.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _slept_calls(captured: list[float]) -> list[float]:
    return list(captured)


def test_parse_returns_codegen_request_and_emits_events(
    sink, clock, intent, llm_response_postgres
) -> None:
    llm = FakeLlmAdapter(responses=[llm_response_postgres])
    svc = IntentInterpretationService(
        llm=llm, validator=None, enhancer=None, events=sink, clock=clock
    )

    request = svc.parse(intent)

    assert request.gvk.kind.value == "PostgresCluster"
    assert {p.name for p in request.spec_properties} == {
        "replicas",
        "storageSize",
        "version",
    }
    sink.assert_events_in_order(
        "IntentSubmitted",
        "LlmInvocationStarted",
        "LlmInvocationSucceeded",
        "CodegenRequestParsed",
    )


def test_parse_translates_legacy_string_property_shape(
    sink, clock, intent
) -> None:
    legacy = {
        "group": "x.example.com",
        "version": "v1",
        "kind": "Foo",
        "spec_properties": {"name": "string", "size": "integer"},
        "description": "Legacy shape.",
        "output_dir": "out",
    }
    llm = FakeLlmAdapter(responses=[legacy])
    svc = IntentInterpretationService(
        llm=llm, validator=None, enhancer=None, events=sink, clock=clock
    )

    request = svc.parse(intent)

    types = {p.name: p.type.value for p in request.spec_properties}
    assert types == {"name": "string", "size": "integer"}


def test_parse_retries_with_backoff_on_rate_limit(
    sink, clock, intent, llm_response_postgres
) -> None:
    captured: list[float] = []
    llm = _RaisingLlm(
        [
            LlmRateLimited("slow down"),
            LlmRateLimited("slow down"),
            llm_response_postgres,
        ]
    )
    svc = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
        sleep=captured.append,
    )

    svc.parse(intent)

    assert llm.calls == 3
    # Backoffs are 2, 4 (third attempt succeeds → no further sleep).
    assert _slept_calls(captured) == [2.0, 4.0]
    failed = sink.events_with_name("LlmInvocationFailed")
    assert len(failed) == 2


def test_parse_gives_up_after_three_rate_limit_retries(
    sink, clock, intent
) -> None:
    captured: list[float] = []
    llm = _RaisingLlm([LlmRateLimited("nope") for _ in range(5)])
    svc = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=None,
        events=sink,
        clock=clock,
        sleep=captured.append,
    )

    with pytest.raises(LlmRateLimited):
        svc.parse(intent)

    assert llm.calls == 4  # 1 initial + 3 retries
    assert _slept_calls(captured) == [2.0, 4.0, 8.0]


def test_parse_propagates_unavailable_for_orchestrator_to_handle(
    sink, clock, intent
) -> None:
    llm = _RaisingLlm([LlmUnavailable("network")])
    svc = IntentInterpretationService(
        llm=llm, validator=None, enhancer=None, events=sink, clock=clock
    )

    with pytest.raises(LlmUnavailable):
        svc.parse(intent)
    assert sink.events_with_name("LlmInvocationFailed")


def test_validate_runs_validator_and_returns_violations(
    sink, clock, intent, llm_response_postgres
) -> None:
    class _ToyValidator:
        def validate(self, request: Any) -> list[FieldViolation]:
            return [
                FieldViolation(
                    path="gvk.kind",
                    expected="non-empty",
                    actual="",
                    message="required",
                )
            ]

    llm = FakeLlmAdapter(responses=[llm_response_postgres])
    svc = IntentInterpretationService(
        llm=llm, validator=_ToyValidator(), enhancer=None, events=sink, clock=clock
    )

    with pytest.raises(DomainValidationError) as excinfo:
        svc.parse(intent)

    assert excinfo.value.field_violations
    assert sink.events_with_name("CodegenRequestRejected")


def test_enhance_passes_through_when_enhancer_absent(
    sink, clock, intent, llm_response_postgres
) -> None:
    llm = FakeLlmAdapter(responses=[llm_response_postgres])
    svc = IntentInterpretationService(
        llm=llm, validator=None, enhancer=None, events=sink, clock=clock
    )
    request = svc.parse(intent)
    assert svc.enhance(request) is request


def test_enhance_calls_enhancer_when_present(
    sink, clock, intent, llm_response_postgres
) -> None:
    class _RecordingEnhancer:
        def __init__(self) -> None:
            self.calls: int = 0

        def enhance(self, request: Any) -> Any:
            self.calls += 1
            return request

    enhancer = _RecordingEnhancer()
    llm = FakeLlmAdapter(responses=[llm_response_postgres])
    svc = IntentInterpretationService(
        llm=llm,
        validator=None,
        enhancer=enhancer,
        events=sink,
        clock=clock,
    )
    svc.parse(intent)
    assert enhancer.calls == 1
