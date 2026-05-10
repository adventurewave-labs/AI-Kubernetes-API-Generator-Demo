"""``LlmProvider`` port.

See ``docs/ddd/07-anti-corruption-layers.md`` section 2 for the rationale
behind a JSON-shaped boundary and the anti-corruption responsibilities of
each adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_platform_generator.domain.values import ProviderMode


@runtime_checkable
class LlmProvider(Protocol):
    """Translate prompts into validated JSON responses.

    The port is **JSON-shaped** on purpose. Domain code never receives a
    raw provider response; an adapter is responsible for stripping any
    non-JSON content and translating provider-specific exceptions to the
    project's error taxonomy before the value crosses this boundary.
    """

    name: str
    model: str
    mode: ProviderMode

    def is_available(self) -> bool:
        """Return ``True`` iff the provider is reachable and credentialled."""

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        """Return a JSON object decoded from the provider's response."""
