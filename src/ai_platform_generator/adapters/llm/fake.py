"""Deterministic in-memory LLM adapter for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 2.2.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_platform_generator.domain.values import ProviderMode


class FakeLlmAdapter:
    """A deterministic ``LlmProvider`` driven by a queue of canned responses.

    Each call to :meth:`complete_json` dequeues the next response. When
    the queue is exhausted, :meth:`is_available` flips to ``False`` and
    further calls raise :class:`RuntimeError` so test failures surface
    loudly rather than silently returning an empty mapping.
    """

    name: str = "fake"
    model: str = "fake-1"

    def __init__(
        self,
        responses: Iterable[Mapping[str, Any]] | None = None,
        mode: ProviderMode | None = None,
    ) -> None:
        self._responses: deque[Mapping[str, Any]] = deque(responses or ())
        self.calls: list[tuple[str, str, Mapping[str, Any] | None, float]] = []
        # ``ProviderMode`` lives in ``domain.values`` which may not be
        # importable while sibling agents work in parallel. Resolve lazily
        # and fall back to the literal ``"live"`` so tests can still
        # construct the adapter.
        if mode is None:
            try:
                from ai_platform_generator.domain.values import ProviderMode

                self.mode: Any = ProviderMode.LIVE
            except Exception:  # pragma: no cover - defensive bootstrap
                self.mode = "live"
        else:
            self.mode = mode

    # ----- public API ---------------------------------------------------

    def enqueue(self, response: Mapping[str, Any]) -> None:
        """Append ``response`` to the queue of canned replies."""
        self._responses.append(response)

    def is_available(self) -> bool:
        return bool(self._responses)

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        self.calls.append((system_prompt, user_prompt, json_schema, timeout_s))
        if not self._responses:
            raise RuntimeError(
                "FakeLlmAdapter: no canned response queued; enqueue() one before calling.",
            )
        return self._responses.popleft()

    # ----- introspection helpers (test-only sugar) ----------------------

    @property
    def remaining(self) -> int:
        """Number of canned responses still queued."""
        return len(self._responses)
