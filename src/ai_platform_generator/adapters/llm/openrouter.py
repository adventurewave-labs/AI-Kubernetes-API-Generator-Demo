"""OpenRouter LLM adapter (live mode).

Implements :class:`LlmProvider` against the OpenRouter API per
:doc:`../../../docs/adr/0003-openrouter-as-primary-llm-provider`.

Uses the official ``openai`` Python SDK pointed at OpenRouter's
``/v1`` endpoint. The adapter performs the anti-corruption duties
described in ``docs/ddd/07-anti-corruption-layers.md`` §2.3:

* translates ``openai`` exception types into our error taxonomy;
* strips Markdown code fences and pre/postambles before JSON parsing;
* enforces a uniform timeout via the SDK's ``timeout`` kwarg;
* never lets a provider-specific exception escape this module.

Substring matching on error messages is **forbidden** — discrimination
is via concrete exception subclasses only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import openai
from openai import OpenAI

from ai_platform_generator.domain.errors import (
    LlmAuthenticationFailed,
    LlmRateLimited,
    LlmResponseUnparseable,
    LlmUnavailable,
    MissingApiKey,
)
from ai_platform_generator.domain.values import ProviderMode

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "meta-llama/llama-3.2-3b-instruct:free"
_PROBE_TIMEOUT_S = 5.0


class OpenRouterLlmAdapter:
    """Live LLM adapter backed by OpenRouter via the ``openai`` SDK.

    Parameters
    ----------
    api_key:
        OpenRouter API key. Must be non-blank or :class:`MissingApiKey`
        is raised at construction time.
    model:
        Default model slug (e.g. ``"meta-llama/llama-3.2-3b-instruct:free"``).
    base_url:
        OpenRouter base URL. Override for tests or self-hosted proxies.
    verify_ssl:
        Whether to verify TLS certificates. Defaults to ``True``;
        ``False`` should only be used for local debugging.
    timeout_s:
        Default per-call timeout in seconds.
    app_name / app_url:
        Sent as ``X-Title`` and ``HTTP-Referer`` headers respectively.
        OpenRouter uses these for analytics and rate-limit attribution.
    """

    name: str = "openrouter"
    mode: ProviderMode = ProviderMode.LIVE

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        verify_ssl: bool = True,
        timeout_s: float = 60.0,
        app_name: str = "ai-platform-generator",
        app_url: str | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise MissingApiKey(
                user_message=(
                    "OpenRouter API key is missing or blank. Set the "
                    "OPENROUTER_API_KEY environment variable, or pass "
                    "--demo to use the offline demo catalogue."
                ),
            )
        self._api_key = api_key
        self.model: str = model
        self._base_url: str = base_url
        self._verify_ssl: bool = verify_ssl
        self._timeout_s: float = float(timeout_s)
        self._app_name: str = app_name
        self._app_url: str | None = app_url

        # Custom httpx client only if we need to disable TLS verification;
        # otherwise let the SDK manage its own pool.
        http_client = None
        if not verify_ssl:
            import httpx

            http_client = httpx.Client(verify=False, timeout=self._timeout_s)

        self._client: OpenAI = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout_s,
            http_client=http_client,
        )
        # Lazy-probe state.
        self._available: bool | None = None
        self._unavailable_reason: str | None = None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """The base URL used by the underlying OpenAI client."""
        return self._base_url

    @property
    def unavailable_reason(self) -> str | None:
        """Reason the last availability probe failed, if any."""
        return self._unavailable_reason

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Lazily probe the provider; cache the result.

        Performs one ``models.list`` call with a short timeout to verify
        credentials. Any exception flips the cache to ``False`` and stores
        the exception's class name in :attr:`unavailable_reason`.
        """
        if self._available is not None:
            return self._available
        try:
            self._client.models.list(timeout=_PROBE_TIMEOUT_S)
        except Exception as exc:  # we *want* to swallow here — see is_available docstring
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
        """Return a JSON object decoded from the model's response.

        OpenRouter exposes per-request OpenAI-style ``response_format``;
        we ask for a JSON object regardless of whether ``json_schema`` is
        supplied because not every OpenRouter-hosted model honours the
        ``json_schema`` flavour. The adapter still strips fences and
        preambles defensively.
        """
        extra_headers: dict[str, str] = {"X-Title": self._app_name}
        if self._app_url:
            extra_headers["HTTP-Referer"] = self._app_url

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=timeout_s,
                extra_headers=extra_headers,
            )
        except openai.AuthenticationError as exc:
            raise LlmAuthenticationFailed(
                "OpenRouter rejected the supplied API key.",
                cause=exc,
            ) from exc
        except openai.RateLimitError as exc:
            raise LlmRateLimited(
                "OpenRouter rate-limited the request.",
                cause=exc,
            ) from exc
        except openai.APITimeoutError as exc:
            raise LlmUnavailable(
                "OpenRouter request timed out.",
                cause=exc,
            ) from exc
        except openai.APIConnectionError as exc:
            raise LlmUnavailable(
                "Could not connect to OpenRouter.",
                cause=exc,
            ) from exc
        except openai.OpenAIError as exc:
            # Catch-all for any other provider error (5xx, malformed
            # responses, etc.). Treated as recoverable / unavailable so
            # the orchestrator can fall back to demo mode.
            raise LlmUnavailable(
                "OpenRouter returned an unexpected provider error.",
                cause=exc,
            ) from exc

        return _parse_response_payload(response)


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _parse_response_payload(response: Any) -> Mapping[str, Any]:
    """Extract the first choice's content and decode JSON.

    Strips Markdown code fences and any preamble/postamble text some
    smaller models emit even with ``response_format=json_object`` set.
    """
    try:
        choice = response.choices[0]
        content = choice.message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LlmResponseUnparseable(
            "OpenRouter response had no choices/content.",
            cause=exc,
        ) from exc
    if content is None or not str(content).strip():
        raise LlmResponseUnparseable("OpenRouter response content was empty.")
    cleaned = _strip_to_json(str(content))
    try:
        decoded = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LlmResponseUnparseable(
            "OpenRouter response was not valid JSON.",
            cause=exc,
        ) from exc
    if not isinstance(decoded, Mapping):
        raise LlmResponseUnparseable(
            f"Expected a JSON object, got {type(decoded).__name__}.",
        )
    return decoded


def _strip_to_json(content: str) -> str:
    """Best-effort cleanup of a model response prior to JSON decoding.

    Removes Markdown code fences (with or without language tags), and if
    the content still has a non-JSON preamble, slices it from the first
    ``{`` to the last ``}``.
    """
    text = content.strip()
    if text.startswith("```"):
        # Drop opening fence (``` or ```json) and trailing fence.
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()
    # Slice to the outer-most braces if there is still preamble.
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]
    return text


__all__ = [
    "OpenRouterLlmAdapter",
]
