"""In-memory ``SecretProvider`` for tests.

See ``docs/ddd/07-anti-corruption-layers.md`` section 5.2.
"""

from __future__ import annotations


class InMemorySecretProvider:
    """Trivial dict-backed :class:`SecretProvider`.

    Constructed from a plain ``dict[str, str]`` so test fixtures can
    declare secrets inline. Mutations to the input dict after
    construction do not affect the provider — the dict is copied.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets or {})

    def get(self, name: str) -> str | None:
        return self._secrets.get(name)

    def names(self) -> list[str]:
        return sorted(self._secrets)
