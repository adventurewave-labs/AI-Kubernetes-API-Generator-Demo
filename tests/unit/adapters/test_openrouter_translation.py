"""Pure-unit tests for :class:`OpenRouterLlmAdapter` exception translation.

We mock the underlying HTTP layer with ``respx`` so the OpenAI SDK
exercises its real exception-raising codepaths without ever touching
the network. The adapter must translate every relevant SDK exception
into our error taxonomy.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from ai_platform_generator.adapters.llm.openrouter import (
    OpenRouterLlmAdapter,
    _strip_to_json,
)
from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
    MissingApiKey,
)
from ai_platform_generator.domain.values import ProviderMode

_BASE_URL = "https://openrouter.ai/api/v1"
_CHAT_ENDPOINT = f"{_BASE_URL}/chat/completions"


def _make_adapter() -> OpenRouterLlmAdapter:
    return OpenRouterLlmAdapter(
        api_key="sk-test",
        model="meta-llama/llama-3.2-3b-instruct:free",
        base_url=_BASE_URL,
        timeout_s=5.0,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_blank_api_key_raises_missing_api_key() -> None:
    with pytest.raises(MissingApiKey):
        OpenRouterLlmAdapter(api_key="")
    with pytest.raises(MissingApiKey):
        OpenRouterLlmAdapter(api_key="   ")


def test_constructed_attributes() -> None:
    adapter = _make_adapter()
    assert adapter.name == "openrouter"
    assert adapter.mode is ProviderMode.LIVE
    assert adapter.model == "meta-llama/llama-3.2-3b-instruct:free"
    assert adapter.base_url == _BASE_URL


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@respx.mock
def test_complete_json_happy_path_returns_decoded_dict() -> None:
    adapter = _make_adapter()
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"hello": "world"}'},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))

    result = adapter.complete_json("system", "user")
    assert result == {"hello": "world"}


@respx.mock
def test_complete_json_strips_code_fence() -> None:
    adapter = _make_adapter()
    fenced = '```json\n{"hello": "fenced"}\n```'
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": fenced},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))
    assert adapter.complete_json("system", "user") == {"hello": "fenced"}


@respx.mock
def test_complete_json_strips_preamble_text() -> None:
    adapter = _make_adapter()
    noisy = 'Sure! Here is the JSON:\n\n{"a": 1}\n\nLet me know if you need more.'
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": noisy},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))
    assert adapter.complete_json("system", "user") == {"a": 1}


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------


@respx.mock
def test_401_translates_to_llm_authentication_failed() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}}),
    )
    with pytest.raises(LlmAuthenticationFailed):
        adapter.complete_json("s", "u")


@respx.mock
def test_429_translates_to_llm_rate_limited() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow down"}}),
    )
    with pytest.raises(LlmRateLimited):
        adapter.complete_json("s", "u")


@respx.mock
def test_500_translates_to_llm_unavailable() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        return_value=httpx.Response(500, json={"error": {"message": "boom"}}),
    )
    with pytest.raises(LlmUnavailable):
        adapter.complete_json("s", "u")


@respx.mock
def test_connect_error_translates_to_llm_unavailable() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        side_effect=httpx.ConnectError("connection refused"),
    )
    with pytest.raises(LlmUnavailable):
        adapter.complete_json("s", "u")


@respx.mock
def test_timeout_translates_to_llm_unavailable() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        side_effect=httpx.ReadTimeout("timed out"),
    )
    with pytest.raises(LlmUnavailable):
        adapter.complete_json("s", "u")


@respx.mock
def test_malformed_json_content_translates_to_unparseable() -> None:
    adapter = _make_adapter()
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "this is not JSON at all"},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(LlmResponseUnparseable):
        adapter.complete_json("s", "u")


@respx.mock
def test_empty_content_translates_to_unparseable() -> None:
    adapter = _make_adapter()
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "   "},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(LlmResponseUnparseable):
        adapter.complete_json("s", "u")


@respx.mock
def test_json_array_not_object_translates_to_unparseable() -> None:
    adapter = _make_adapter()
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 0,
        "model": adapter.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "[1, 2, 3]"},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post(_CHAT_ENDPOINT).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(LlmResponseUnparseable):
        adapter.complete_json("s", "u")


# ---------------------------------------------------------------------------
# is_available probe
# ---------------------------------------------------------------------------


@respx.mock
def test_is_available_true_when_models_list_succeeds() -> None:
    adapter = _make_adapter()
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "m"}]}),
    )
    assert adapter.is_available() is True
    # Cached: a second call should not re-fetch.
    assert adapter.is_available() is True


@respx.mock
def test_is_available_false_on_error_and_caches_reason() -> None:
    adapter = _make_adapter()
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(401, json={"error": {"message": "nope"}}),
    )
    assert adapter.is_available() is False
    assert adapter.unavailable_reason is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_strip_to_json_handles_fences_and_preamble() -> None:
    assert _strip_to_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_to_json("Here you go: {\"x\": 2} thanks!") == '{"x": 2}'
    # Already-clean JSON passes through.
    assert _strip_to_json('{"clean": true}') == '{"clean": true}'
    # No braces at all → returned unchanged.
    assert _strip_to_json("nothing here") == "nothing here"
