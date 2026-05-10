"""Process-environment :class:`SecretProvider` adapter.

See ADR-0012 (env vars are the canonical secret surface) and
``docs/ddd/07-anti-corruption-layers.md`` §5.

The default :meth:`names` pattern matches the conventional suffixes
used by the keys this project consumes: ``*_API_KEY``, ``*_TOKEN``,
``*_SECRET``. Anyone wiring a more permissive provider can pass a
custom regex.
"""

from __future__ import annotations

import os
import re
from re import Pattern

#: Default suffix pattern. Matches ``OPENAI_API_KEY``,
#: ``ANTHROPIC_API_KEY``, ``GITHUB_TOKEN``, ``MY_APP_SECRET``, etc.
DEFAULT_NAME_PATTERN: Pattern[str] = re.compile(
    r".*(?:_API_KEY|_TOKEN|_SECRET)$"
)


class EnvSecretProvider:
    """Resolve secrets from :data:`os.environ`.

    Parameters
    ----------
    pattern:
        Compiled regex used by :meth:`names` to enumerate secret-shaped
        env vars. The pattern is anchored with ``fullmatch`` semantics
        — any pattern matching the *entire* env-var name is considered
        a secret.
    environ:
        Optional mapping for tests; defaults to :data:`os.environ`.
    """

    def __init__(
        self,
        *,
        pattern: Pattern[str] | str = DEFAULT_NAME_PATTERN,
        environ: dict[str, str] | None = None,
    ) -> None:
        self._pattern: Pattern[str] = (
            re.compile(pattern) if isinstance(pattern, str) else pattern
        )
        # ``os.environ`` is treated live (we do not snapshot at construction).
        # When ``environ`` is supplied for tests we keep the reference so
        # mutations during the test are observable.
        self._environ = environ if environ is not None else os.environ

    def get(self, name: str) -> str | None:
        """Return the env-var value for ``name`` or ``None`` if absent."""
        if not isinstance(name, str):
            return None
        value = self._environ.get(name)
        return value if value is not None else None

    def names(self) -> list[str]:
        """Return env-var names matching the configured secret pattern.

        Sorted lexicographically for deterministic test output.
        """
        return sorted(
            n for n in self._environ if self._pattern.fullmatch(n) is not None
        )


__all__ = ["DEFAULT_NAME_PATTERN", "EnvSecretProvider"]
