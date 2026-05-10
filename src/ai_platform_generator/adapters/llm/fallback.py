"""Composite ``LlmProvider`` with retry + demo fallback.

Implements the retry-with-backoff and demo-fallback policy described in
:doc:`../../../docs/adr/0009-graceful-degradation-to-demo-mode` and
``docs/ddd/06-application-services.md`` §4.

Policy
------
* :class:`LlmRateLimited` from the primary triggers exponential backoff
  (2, 4, 8 seconds) up to 3 attempts. If still rate-limited after the
  third attempt, control passes to the fallback.
* :class:`LlmUnavailable` and :class:`LlmAuthenticationFailed` from the
  primary are terminal for the primary — control passes to the fallback
  immediately and a :class:`DemoModeEngaged` event is published if an
  :class:`EventBus` was injected.
* :class:`LlmResponseUnparseable` is *not* swapped — it indicates the
  provider responded but produced bogus content, which is a different
  failure mode (and the orchestrator may retry the prompt). It is
  re-raised unchanged.
* All other exceptions propagate.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmUnavailable,
)
from ai_platform_generator.domain.events import DemoModeEngaged
from ai_platform_generator.domain.values import ProviderMode

if TYPE_CHECKING:  # pragma: no cover
    from ai_platform_generator.domain.events import EventBus
    from ai_platform_generator.ports import LlmProvider


# Backoff schedule in seconds. Exposed module-level so tests can monkey-patch
# the surrounding ``time.sleep`` rather than this constant.
_BACKOFF_SCHEDULE_S: tuple[float, ...] = (2.0, 4.0, 8.0)


class FallbackLlmProvider:
    """Wrap a primary ``LlmProvider`` with a fallback (typically demo mode).

    Parameters
    ----------
    primary:
        The "real" provider (e.g. :class:`OpenRouterLlmAdapter`).
    fallback:
        A provider to use when the primary is permanently or temporarily
        unusable — usually :class:`DemoModeLlmAdapter`.
    event_bus:
        Optional :class:`EventBus` for publishing
        :class:`DemoModeEngaged` when the fallback takes over.
    """

    def __init__(
        self,
        primary: LlmProvider,
        fallback: LlmProvider,
        *,
        event_bus: EventBus | None = None,
    ) -> None:
        self._primary: LlmProvider = primary
        self._fallback: LlmProvider = fallback
        self._event_bus: EventBus | None = event_bus
        self.name: str = f"{primary.name}+{fallback.name}"
        # Track which provider served the most recent successful call.
        self._last_mode_used: ProviderMode = primary.mode

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def primary(self) -> LlmProvider:
        return self._primary

    @property
    def fallback(self) -> LlmProvider:
        return self._fallback

    @property
    def model(self) -> str:
        """Return the primary's current model id (live preference)."""
        return self._primary.model

    @property
    def mode(self) -> ProviderMode:
        """The mode of the provider that served the most recent call."""
        return self._last_mode_used

    @property
    def last_mode_used(self) -> ProviderMode:
        return self._last_mode_used

    # ------------------------------------------------------------------
    # LlmProvider surface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Always ``True`` — the fallback is presumed always available."""
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        primary_failure: Exception | None = None
        primary_failure_kind: str | None = None

        # ---- attempt primary, with retry on rate-limit -----------------
        for attempt in range(len(_BACKOFF_SCHEDULE_S) + 1):
            try:
                result = self._primary.complete_json(
                    system_prompt,
                    user_prompt,
                    json_schema,
                    timeout_s,
                )
            except LlmRateLimited as exc:
                if attempt >= len(_BACKOFF_SCHEDULE_S):
                    primary_failure = exc
                    primary_failure_kind = "rate_limited"
                    break
                time.sleep(_BACKOFF_SCHEDULE_S[attempt])
                continue
            except (LlmUnavailable, LlmAuthenticationFailed) as exc:
                primary_failure = exc
                primary_failure_kind = (
                    "auth_failed"
                    if isinstance(exc, LlmAuthenticationFailed)
                    else "unavailable"
                )
                break
            else:
                self._last_mode_used = self._primary.mode
                return result

        # ---- primary failed terminally → engage fallback ---------------
        assert primary_failure is not None  # narrows type for mypy/readers
        self._publish_demo_engaged(
            reason=primary_failure_kind or "unknown",
            primary_name=self._primary.name,
            fallback_name=self._fallback.name,
        )
        result = self._fallback.complete_json(
            system_prompt,
            user_prompt,
            json_schema,
            timeout_s,
        )
        self._last_mode_used = self._fallback.mode
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _publish_demo_engaged(
        self,
        *,
        reason: str,
        primary_name: str,
        fallback_name: str,
    ) -> None:
        if self._event_bus is None:
            return
        event = DemoModeEngaged.make(
            run_id=None,
            payload={
                "reason": reason,
                "primary": primary_name,
                "fallback": fallback_name,
            },
        )
        self._event_bus.publish(event)


__all__ = [
    "FallbackLlmProvider",
]
