"""Composite first-hit-wins :class:`SecretProvider` adapter.

The default wiring in ``application/composition.py`` uses a chain of
``[Env, Dotenv, ...optional...]`` providers; ADR-0012 calls out the
order: process env first, then ``.env``, then any plug-in providers.
"""

from __future__ import annotations

from collections.abc import Iterable

from ai_platform_generator.ports.secret_provider import SecretProvider


class ChainSecretProvider:
    """Compose multiple :class:`SecretProvider` instances.

    :meth:`get` returns the value from the first provider that yields a
    non-``None`` result. :meth:`names` returns the de-duplicated, sorted
    union of every constituent provider's names.

    Parameters
    ----------
    providers:
        Iterable of providers, evaluated in order. The iterable is
        materialised once at construction so re-iteration of a generator
        does not surprise callers.
    """

    def __init__(self, providers: Iterable[SecretProvider]) -> None:
        self._providers: tuple[SecretProvider, ...] = tuple(providers)

    def get(self, name: str) -> str | None:
        for provider in self._providers:
            value = provider.get(name)
            if value is not None:
                return value
        return None

    def names(self) -> list[str]:
        seen: set[str] = set()
        for provider in self._providers:
            seen.update(provider.names())
        return sorted(seen)


__all__ = ["ChainSecretProvider"]
