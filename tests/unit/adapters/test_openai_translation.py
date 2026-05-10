"""Pure-unit tests for :class:`OpenAiLlmAdapter` exception translation.

Mirrors :file:`test_openrouter_translation.py` but talks to a custom
``base_url`` so we can mock the HTTP layer with respx. The translation
table is identical to OpenRouter's; the differences exercised here are
construction (no extra OpenRouter headers) and the ``json_schema``
response-format branch.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from ai_platform_generator.adapters.llm.openai_direct import OpenAiLlmAdapter
from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
    MissingApiKey,
)
from ai_platform_generator.domain.values import ProviderMode

_BASE_URL = "https://api.openai.test/v1"
_CHAT_ENDPOINT = f"{_BASE_URL}/chat/completions"


def _make_adapter() -> OpenAiLlmAdapter:
    return OpenAiLlmAdapter(
        api_key="sk-test",
        model="gpt-4o-mini",
        base_url=_BASE_URL,
        timeout_s=5.0,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_blank_api_key_raises_missing_api_key() -> None:
    with pytest.raises(MissingApiKey):
        OpenAiLlmAdapter(api_key="")
    with pytest.raises(MissingApiKey):
        OpenAiLlmAdapter(api_key="\t  ")


def test_constructed_attributes() -> None:
    adapter = _make_adapter()
    assert adapter.name == "openai"
    assert adapter.mode is ProviderMode.LIVE
    assert adapter.model == "gpt-4o-mini"


def test_default_base_url_is_sdk_default() -> None:
    # base_url=None means use the SDK default. The adapter shouldn't crash.
    adapter = OpenAiLlmAdapter(api_key="sk-test", base_url=None)
    assert adapter is not None


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

    assert adapter.complete_json("s", "u") == {"hello": "world"}


@respx.mock
def test_complete_json_uses_json_schema_response_format_when_provided() -> None:
    adapter = _make_adapter()
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "1",
                "object": "chat.completion",
                "created": 0,
                "model": adapter.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"x": 1}',
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    respx.post(_CHAT_ENDPOINT).mock(side_effect=_handler)

    schema = {
        "name": "demo",
        "schema": {"type": "object", "properties": {"x": {"type": "integer"}}},
    }
    out = adapter.complete_json("s", "u", json_schema=schema)
    assert out == {"x": 1}
    response_format = captured["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "demo"


@respx.mock
def test_complete_json_uses_json_object_when_no_schema_provided() -> None:
    adapter = _make_adapter()
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "1",
                "object": "chat.completion",
                "created": 0,
                "model": adapter.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"y": 2}'},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    respx.post(_CHAT_ENDPOINT).mock(side_effect=_handler)
    adapter.complete_json("s", "u")
    response_format = captured["response_format"]
    assert isinstance(response_format, dict)
    assert response_format == {"type": "json_object"}


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------


@respx.mock
def test_401_translates_to_llm_authentication_failed() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad"}}),
    )
    with pytest.raises(LlmAuthenticationFailed):
        adapter.complete_json("s", "u")


@respx.mock
def test_429_translates_to_llm_rate_limited() -> None:
    adapter = _make_adapter()
    respx.post(_CHAT_ENDPOINT).mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow"}}),
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
                "message": {"role": "assistant", "content": "definitely not json"},
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
                "message": {"role": "assistant", "content": ""},
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


@respx.mock
def test_is_available_false_on_401_and_caches_reason() -> None:
    adapter = _make_adapter()
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(401, json={"error": {"message": "nope"}}),
    )
    assert adapter.is_available() is False
    assert adapter.unavailable_reason is not None
