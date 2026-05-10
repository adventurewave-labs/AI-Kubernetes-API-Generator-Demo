"""Tests for :class:`FallbackLlmProvider`.

Uses a small in-memory ``LlmProvider`` stub to exercise:

* the happy path (primary serves the call);
* exponential-backoff retry on :class:`LlmRateLimited`;
* fallback engagement on :class:`LlmUnavailable` /
  :class:`LlmAuthenticationFailed`;
* :class:`DemoModeEngaged` event publication;
* ``last_mode_used`` / ``mode`` reflect the provider that ultimately
  served the call.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from ai_platform_generator.adapters.llm.fallback import FallbackLlmProvider
from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
)
from ai_platform_generator.domain.events import DemoModeEngaged, EventBus
from ai_platform_generator.domain.values import ProviderMode


class _ScriptedProvider:
    """A scripted ``LlmProvider`` for testing.

    ``responses`` is a list of either:
    * a ``Mapping`` — returned from the next ``complete_json`` call;
    * an ``Exception`` instance — raised from the next call.
    """

    def __init__(
        self,
        *,
        name: str,
        mode: ProviderMode,
        responses: list[Any] | None = None,
    ) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.mode = mode
        self._responses: list[Any] = list(responses or [])
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        self.calls += 1
        if not self._responses:
            raise AssertionError(
                f"{self.name}: ran out of scripted responses on call {self.calls}",
            )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_primary_success_returns_primary_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    primary = _ScriptedProvider(
        name="prim", mode=ProviderMode.LIVE, responses=[{"ok": True}],
    )
    fallback = _ScriptedProvider(name="dem", mode=ProviderMode.DEMO)

    provider = FallbackLlmProvider(primary, fallback)
    assert provider.is_available() is True
    assert provider.complete_json("s", "u") == {"ok": True}
    assert primary.calls == 1
    assert fallback.calls == 0
    assert sleeps == []
    assert provider.last_mode_used is ProviderMode.LIVE
    assert provider.mode is ProviderMode.LIVE


def test_name_concatenates_primary_and_fallback() -> None:
    primary = _ScriptedProvider(name="prim", mode=ProviderMode.LIVE)
    fallback = _ScriptedProvider(name="dem", mode=ProviderMode.DEMO)
    provider = FallbackLlmProvider(primary, fallback)
    assert provider.name == "prim+dem"


# ---------------------------------------------------------------------------
# Rate-limit retry path
# ---------------------------------------------------------------------------


def test_rate_limited_retries_with_backoff_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[
            LlmRateLimited("429"),
            LlmRateLimited("429 again"),
            {"ok": "after-retry"},
        ],
    )
    fallback = _ScriptedProvider(name="dem", mode=ProviderMode.DEMO)
    provider = FallbackLlmProvider(primary, fallback)

    out = provider.complete_json("s", "u")
    assert out == {"ok": "after-retry"}
    # Two sleeps before the third (successful) attempt.
    assert sleeps == [2.0, 4.0]
    assert primary.calls == 3
    assert fallback.calls == 0
    assert provider.last_mode_used is ProviderMode.LIVE


def test_rate_limited_after_three_retries_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[
            LlmRateLimited("1"),
            LlmRateLimited("2"),
            LlmRateLimited("3"),
            LlmRateLimited("4"),  # final attempt also rate-limited
        ],
    )
    fallback = _ScriptedProvider(
        name="dem", mode=ProviderMode.DEMO, responses=[{"served-by": "demo"}],
    )
    bus = EventBus()
    received: list[Any] = []
    bus.subscribe(received.append)

    provider = FallbackLlmProvider(primary, fallback, event_bus=bus)
    out = provider.complete_json("s", "u")

    assert out == {"served-by": "demo"}
    # 3 sleeps between 4 attempts.
    assert sleeps == [2.0, 4.0, 8.0]
    assert primary.calls == 4
    assert fallback.calls == 1
    assert provider.last_mode_used is ProviderMode.DEMO
    assert provider.mode is ProviderMode.DEMO

    # DemoModeEngaged event was published with reason=rate_limited.
    demo_events = [e for e in received if isinstance(e, DemoModeEngaged)]
    assert len(demo_events) == 1
    assert demo_events[0].payload["reason"] == "rate_limited"
    assert demo_events[0].payload["primary"] == "prim"
    assert demo_events[0].payload["fallback"] == "dem"


# ---------------------------------------------------------------------------
# Terminal primary failures → fallback
# ---------------------------------------------------------------------------


def test_unavailable_falls_back_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[LlmUnavailable("network gone")],
    )
    fallback = _ScriptedProvider(
        name="dem", mode=ProviderMode.DEMO, responses=[{"src": "demo"}],
    )
    bus = EventBus()
    received: list[Any] = []
    bus.subscribe(received.append)
    provider = FallbackLlmProvider(primary, fallback, event_bus=bus)

    out = provider.complete_json("s", "u")
    assert out == {"src": "demo"}
    # No retry sleeps for unavailable.
    assert sleeps == []
    assert primary.calls == 1
    assert fallback.calls == 1
    assert provider.last_mode_used is ProviderMode.DEMO

    demo_events = [e for e in received if isinstance(e, DemoModeEngaged)]
    assert len(demo_events) == 1
    assert demo_events[0].payload["reason"] == "unavailable"


def test_auth_failed_falls_back_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[LlmAuthenticationFailed("bad key")],
    )
    fallback = _ScriptedProvider(
        name="dem", mode=ProviderMode.DEMO, responses=[{"src": "demo"}],
    )
    bus = EventBus()
    received: list[Any] = []
    bus.subscribe(received.append)
    provider = FallbackLlmProvider(primary, fallback, event_bus=bus)

    out = provider.complete_json("s", "u")
    assert out == {"src": "demo"}
    assert primary.calls == 1
    assert fallback.calls == 1

    demo_events = [e for e in received if isinstance(e, DemoModeEngaged)]
    assert len(demo_events) == 1
    assert demo_events[0].payload["reason"] == "auth_failed"


def test_no_event_bus_means_no_event_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[LlmUnavailable("boom")],
    )
    fallback = _ScriptedProvider(
        name="dem", mode=ProviderMode.DEMO, responses=[{"x": 1}],
    )
    provider = FallbackLlmProvider(primary, fallback)
    out = provider.complete_json("s", "u")
    assert out == {"x": 1}


# ---------------------------------------------------------------------------
# Errors that should not trigger fallback
# ---------------------------------------------------------------------------


def test_unparseable_response_propagates_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[LlmResponseUnparseable("bad json")],
    )
    fallback = _ScriptedProvider(name="dem", mode=ProviderMode.DEMO)
    provider = FallbackLlmProvider(primary, fallback)

    with pytest.raises(LlmResponseUnparseable):
        provider.complete_json("s", "u")
    assert fallback.calls == 0


def test_unrelated_exception_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[ValueError("boom")],
    )
    fallback = _ScriptedProvider(name="dem", mode=ProviderMode.DEMO)
    provider = FallbackLlmProvider(primary, fallback)

    with pytest.raises(ValueError):
        provider.complete_json("s", "u")
    assert fallback.calls == 0


# ---------------------------------------------------------------------------
# Mode tracking after mixed calls
# ---------------------------------------------------------------------------


def test_mode_tracks_most_recent_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    primary = _ScriptedProvider(
        name="prim",
        mode=ProviderMode.LIVE,
        responses=[
            {"first": True},  # success
            LlmUnavailable("boom"),  # then fall back
            {"third": True},  # success again
        ],
    )
    fallback = _ScriptedProvider(
        name="dem", mode=ProviderMode.DEMO, responses=[{"second": True}],
    )
    provider = FallbackLlmProvider(primary, fallback)

    assert provider.complete_json("s", "u") == {"first": True}
    assert provider.last_mode_used is ProviderMode.LIVE
    assert provider.complete_json("s", "u") == {"second": True}
    assert provider.last_mode_used is ProviderMode.DEMO
    assert provider.complete_json("s", "u") == {"third": True}
    assert provider.last_mode_used is ProviderMode.LIVE
