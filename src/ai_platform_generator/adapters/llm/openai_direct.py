"""OpenAI direct LLM adapter (live mode).

Mirrors :class:`OpenRouterLlmAdapter` but talks directly to OpenAI's
default endpoint. The notable difference is that, when a JSON schema is
supplied via ``complete_json(json_schema=...)``, this adapter uses
OpenAI's structured-output mode (``response_format={"type":
"json_schema", ...}``) for tighter validation. Without a schema it falls
back to ``response_format={"type": "json_object"}`` like its OpenRouter
sibling.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

import openai
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from ai_platform_generator.adapters.llm.openrouter import _strip_to_json
from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
    MissingApiKey,
)
from ai_platform_generator.domain.values import ProviderMode

_DEFAULT_MODEL = "gpt-4o-mini"
_PROBE_TIMEOUT_S = 5.0


class OpenAiLlmAdapter:
    """Live LLM adapter backed by OpenAI's hosted API.

    Parameters mirror :class:`OpenRouterLlmAdapter` except ``base_url``
    defaults to the SDK default (``None``) and there are no
    OpenRouter-specific headers.
    """

    name: str = "openai"
    mode: ProviderMode = ProviderMode.LIVE

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str | None = None,
        verify_ssl: bool = True,
        timeout_s: float = 60.0,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise MissingApiKey(
                user_message=(
                    "OpenAI API key is missing or blank. Set the "
                    "OPENAI_API_KEY environment variable, or pass "
                    "--demo to use the offline demo catalogue."
                ),
            )
        self._api_key = api_key
        self.model: str = model
        self._base_url = base_url
        self._verify_ssl = verify_ssl
        self._timeout_s = float(timeout_s)

        http_client = None
        if not verify_ssl:
            import httpx

            http_client = httpx.Client(verify=False, timeout=self._timeout_s)

        client_kwargs: dict[str, Any] = {
            "api_key": self._api_key,
            "timeout": self._timeout_s,
        }
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        self._client: OpenAI = OpenAI(**client_kwargs)

        self._available: bool | None = None
        self._unavailable_reason: str | None = None

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            self._client.models.list(timeout=_PROBE_TIMEOUT_S)
        except Exception as exc:  # intentional swallow — see is_available docstring
            self._available = False
            self._unavailable_reason = type(exc).__name__
            return False
        self._available = True
        self._unavailable_reason = None
        return True

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Mapping[str, Any] | None = None,
        timeout_s: float = 60.0,
    ) -> Mapping[str, Any]:
        if json_schema is not None:
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": dict(json_schema),
            }
        else:
            response_format = {"type": "json_object"}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Cast: ``messages`` is a list of plain dicts here. The
            # OpenAI SDK declares the typed-dict variants of
            # :class:`ChatCompletionMessageParam`; structurally identical.
            response = self._client.chat.completions.create(
                model=self.model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                response_format=cast(Any, response_format),
                temperature=0.1,
                timeout=timeout_s,
            )
        except openai.AuthenticationError as exc:
            raise LlmAuthenticationFailed(
                "OpenAI rejected the supplied API key.",
                cause=exc,
            ) from exc
        except openai.RateLimitError as exc:
            raise LlmRateLimited(
                "OpenAI rate-limited the request.",
                cause=exc,
            ) from exc
        except openai.APITimeoutError as exc:
            raise LlmUnavailable(
                "OpenAI request timed out.",
                cause=exc,
            ) from exc
        except openai.APIConnectionError as exc:
            raise LlmUnavailable(
                "Could not connect to OpenAI.",
                cause=exc,
            ) from exc
        except openai.OpenAIError as exc:
            raise LlmUnavailable(
                "OpenAI returned an unexpected provider error.",
                cause=exc,
            ) from exc

        return _parse_response_payload(response)


def _parse_response_payload(response: Any) -> Mapping[str, Any]:
    """Decode the first choice's content as JSON, defensively cleaned."""
    try:
        choice = response.choices[0]
        content = choice.message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LlmResponseUnparseable(
            "OpenAI response had no choices/content.",
            cause=exc,
        ) from exc
    if content is None or not str(content).strip():
        raise LlmResponseUnparseable("OpenAI response content was empty.")
    cleaned = _strip_to_json(str(content))
    try:
        decoded = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LlmResponseUnparseable(
            "OpenAI response was not valid JSON.",
            cause=exc,
        ) from exc
    if not isinstance(decoded, Mapping):
        raise LlmResponseUnparseable(
            f"Expected a JSON object, got {type(decoded).__name__}.",
        )
    return decoded


__all__ = [
    "OpenAiLlmAdapter",
]
