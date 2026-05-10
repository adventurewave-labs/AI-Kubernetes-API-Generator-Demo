"""Intent-interpretation errors.

These cover the path between *user free-text* and a validated
``CodegenRequest``. Several of them are recoverable: the orchestrator may
retry with backoff or fall back to demo mode (see ADR-0009, ADR-0016).
"""
from __future__ import annotations

from .base import PlatformGeneratorError


class IntentInterpretationError(PlatformGeneratorError):
    """Base class for failures while interpreting a user intent."""

    code = "E_INTENT_GENERIC"


class LlmUnavailable(IntentInterpretationError):
    """The LLM provider could not be reached at all (network, DNS, 5xx).

    Recoverable: the orchestrator should retry with backoff and may fall
    back to demo mode if retries are exhausted.
    """

    code = "E_INTENT_LLM_UNAVAILABLE"
    recoverable = True


class LlmAuthenticationFailed(IntentInterpretationError):
    """The provider rejected our credentials (401/403)."""

    code = "E_INTENT_LLM_AUTH_FAILED"


class LlmRateLimited(IntentInterpretationError):
    """The provider returned a rate-limit response (429).

    Recoverable: the orchestrator should back off and retry.
    """

    code = "E_INTENT_LLM_RATE_LIMITED"
    recoverable = True


class LlmResponseUnparseable(IntentInterpretationError):
    """The LLM responded but the content could not be parsed into JSON / IR."""

    code = "E_INTENT_LLM_UNPARSEABLE"


class AmbiguousIntent(IntentInterpretationError):
    """The user's intent could be parsed but admits multiple valid GVKs."""

    code = "E_INTENT_AMBIGUOUS"
