"""Secret redaction policy and engine.

Implements the redaction rules from
``docs/ddd/bounded-contexts/06-observability.md`` section 9 and
ADR-0017 / ADR-0020 ("Secret hygiene"). The redactor runs **before**
any sink sees the payload, so neither structured logs nor OTEL spans
nor metric labels can leak the strings we know how to recognise.

Design notes
------------
* The policy is a plain frozen dataclass so it can be cached / shared
  freely between sinks.
* ``redact_string`` and ``redact_mapping`` never mutate their input.
* Redaction is **idempotent** by construction: the replacement
  literal ``"[REDACTED]"`` does not match any default pattern, and
  re-walking an already-redacted mapping is a no-op.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

REDACTED: str = "[REDACTED]"

# The default regex catalogue. Compiled once at import time so the
# patterns are shared between every :class:`RedactionPolicy.default()`
# instance.
_DEFAULT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"or-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer [A-Za-z0-9._\-]+"),
)

_DEFAULT_SECRET_KEYS: tuple[str, ...] = (
    "api_key",
    "secret",
    "token",
    "password",
)

_ENV_PATTERNS: str = "AI_AGENT_REDACT_PATTERNS"


@dataclass(frozen=True)
class RedactionPolicy:
    """A frozen bundle of regex patterns + secret-key names.

    Attributes
    ----------
    patterns:
        Compiled regular expressions whose matches are replaced with
        the literal ``"[REDACTED]"`` inside string values.
    secret_keys:
        Keys whose *values* are unconditionally replaced with
        ``"[REDACTED]"`` regardless of type. Matching is
        case-insensitive — see :meth:`SecretRedactor.redact_mapping`.
    """

    patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)
    secret_keys: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls) -> RedactionPolicy:
        """Return the spec defaults from ``06-observability.md`` §9."""
        return cls(patterns=_DEFAULT_PATTERNS, secret_keys=_DEFAULT_SECRET_KEYS)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> RedactionPolicy:
        """Return :meth:`default` plus regex patterns from the environment.

        ``AI_AGENT_REDACT_PATTERNS`` is a comma-separated list of
        Python regex strings. Whitespace around each entry is stripped
        and empty entries are skipped. Patterns that fail to compile
        are dropped silently to avoid weaponising a bad env var into a
        runtime crash — the operator can always inspect the policy via
        :pyattr:`RedactionPolicy.patterns` if they need to confirm
        which extra rules are active.
        """
        source: Mapping[str, str] = env if env is not None else os.environ
        raw = source.get(_ENV_PATTERNS, "")
        extras: list[re.Pattern[str]] = []
        for fragment in raw.split(","):
            stripped = fragment.strip()
            if not stripped:
                continue
            try:
                extras.append(re.compile(stripped))
            except re.error:
                # See module docstring: never crash on a bad env-var.
                continue
        return cls(
            patterns=tuple(_DEFAULT_PATTERNS) + tuple(extras),
            secret_keys=_DEFAULT_SECRET_KEYS,
        )


class SecretRedactor:
    """Apply a :class:`RedactionPolicy` to strings and nested mappings.

    Public surface:

    * :meth:`redact_string` — substitute every regex match with
      ``"[REDACTED]"``.
    * :meth:`redact_mapping` — recursively walk a mapping; values
      under any key in :pyattr:`RedactionPolicy.secret_keys` are
      replaced wholesale, every other string value is run through
      :meth:`redact_string`. Lists / tuples / nested mappings recurse.

    The redactor is idempotent: redacting an already-redacted value
    yields an equal value.
    """

    def __init__(self, policy: RedactionPolicy) -> None:
        self._policy = policy
        # Lower-cased once so :meth:`redact_mapping` can do an
        # ``in``-check without re-lowercasing each key per call.
        self._secret_keys_lc: frozenset[str] = frozenset(
            key.lower() for key in policy.secret_keys
        )

    # ----- public API --------------------------------------------------

    @property
    def policy(self) -> RedactionPolicy:
        return self._policy

    def redact_string(self, value: str) -> str:
        """Replace every pattern match in ``value`` with ``"[REDACTED]"``."""
        if not isinstance(value, str):  # pragma: no cover - defensive
            return value
        result = value
        for pattern in self._policy.patterns:
            result = pattern.sub(REDACTED, result)
        return result

    def redact_mapping(self, mapping: Mapping[str, Any]) -> dict[str, Any]:
        """Return a deep-redacted copy of ``mapping``."""
        return self._redact_mapping(mapping)

    # ----- internals ---------------------------------------------------

    def _redact_mapping(self, mapping: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in mapping.items():
            if isinstance(key, str) and key.lower() in self._secret_keys_lc:
                # Whole-value redaction regardless of type so callers
                # cannot accidentally smuggle a secret through as a
                # nested dict / list payload.
                out[key] = REDACTED
                continue
            out[key] = self._redact_value(value)
        return out

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact_string(value)
        if isinstance(value, Mapping):
            return self._redact_mapping(value)
        if isinstance(value, list):
            return [self._redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._redact_value(item) for item in value)
        return value
