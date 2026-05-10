"""Deterministic in-process LLM adapter — the demo-mode fallback.

Implements :class:`LlmProvider` per :doc:`../../../docs/adr/0009-graceful-degradation-to-demo-mode`.
The adapter has no network dependencies, is *always* available, and
returns a curated :class:`CodegenRequest`-shaped JSON payload chosen by
keyword-matching the user prompt against a :class:`DemoCatalog`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.values import ProviderMode


class DemoModeLlmAdapter:
    """An always-available, deterministic ``LlmProvider`` fallback.

    Construction is cheap; no I/O is performed at any point. Each call
    to :meth:`complete_json` selects a :class:`DemoScenario` from the
    catalogue using keyword-matching on the ``user_prompt`` and returns
    the scenario's pre-validated request payload.
    """

    name: str = "demo"
    model: str = "demo-catalog-v1"

    def __init__(self, catalog: DemoCatalog | None = None) -> None:
        self._catalog: DemoCatalog = catalog if catalog is not None else DemoCatalog()
        self.mode: ProviderMode = ProviderMode.DEMO
        # Test/diagnostic surface: which scenario was last served.
        self._last_scenario_name: str | None = None

    @property
    def catalog(self) -> DemoCatalog:
        """The catalogue this adapter is reading from."""
        return self._catalog

    @property
    def last_scenario_name(self) -> str | None:
        """Name of the scenario served by the most recent call."""
        return self._last_scenario_name

    def is_available(self) -> bool:
        """Demo mode never fails; always returns ``True``."""
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        """Return the request payload for the matching demo scenario.

        Falls back to the catalogue's default scenario (``vector-db`` by
        default) when no keyword matches the ``user_prompt``.
        """
        scenario = self._catalog.find(user_prompt)
        self._last_scenario_name = scenario.name
        # Return a defensive copy so callers can't mutate the catalogue.
        return dict(scenario.request)


__all__ = ["DemoModeLlmAdapter"]
