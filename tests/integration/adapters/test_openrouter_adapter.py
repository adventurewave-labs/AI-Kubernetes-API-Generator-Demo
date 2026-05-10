"""Integration test for :class:`OpenRouterLlmAdapter`.

Skipped unless ``OPENROUTER_API_KEY`` is set in the environment. Hits
the real OpenRouter endpoint with a small free-tier model and verifies
a single happy-path JSON completion.
"""

from __future__ import annotations

import os

import pytest

from ai_platform_generator.adapters.llm.openrouter import OpenRouterLlmAdapter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY is not set",
    ),
]


def test_openrouter_complete_json_happy_path() -> None:
    api_key = os.environ["OPENROUTER_API_KEY"]
    adapter = OpenRouterLlmAdapter(
        api_key=api_key,
        model=os.environ.get(
            "OPENROUTER_MODEL",
            "meta-llama/llama-3.2-3b-instruct:free",
        ),
        timeout_s=30.0,
    )

    assert adapter.is_available() is True

    payload = adapter.complete_json(
        system_prompt=(
            'You are a JSON generator. Always respond with a JSON object '
            'with a single key "ok" set to true.'
        ),
        user_prompt='Respond with {"ok": true}',
        timeout_s=30.0,
    )
    assert isinstance(payload, dict)
    # We don't assert exact equality — small models can be quirky — but
    # we expect a non-empty dict response.
    assert payload  # non-empty
