"""OS-keychain :class:`SecretProvider` adapter.

Backed by the `keyring <https://pypi.org/project/keyring/>`_ package, which
abstracts over macOS Keychain, Windows Credential Locker, and the
SecretService API on Linux.

``keyring`` is an **optional** dependency. If the import fails the
module exposes a stub :class:`KeyringSecretProvider` whose constructor
raises :class:`ConfigurationError` so a misconfiguration is loud rather
than silently broken.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING

from ai_platform_generator.domain.errors import ConfigurationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


_keyring: ModuleType | None
_keyring_errors: ModuleType | None
try:  # pragma: no cover - exercised by import-side tests when keyring is present
    import keyring as _keyring_module
    import keyring.errors as _keyring_errors_module

    _keyring = _keyring_module
    _keyring_errors = _keyring_errors_module
    _KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover
    _keyring = None
    _keyring_errors = None
    _KEYRING_AVAILABLE = False


_DEFAULT_SERVICE = "ai-platform-generator"


if _KEYRING_AVAILABLE:

    class KeyringSecretProvider:
        """Resolve secrets from the OS keychain under a configurable service.

        Parameters
        ----------
        service_name:
            The keyring "service" namespace. Defaults to
            ``"ai-platform-generator"``. Multiple services can co-exist
            on a single keychain so test deployments may use a unique
            value.
        names:
            Optional iterable of secret names. If supplied, :meth:`names`
            returns these verbatim; otherwise it returns an empty list
            (the OS keychain has no enumeration API on every platform).
        """

        def __init__(
            self,
            *,
            service_name: str = _DEFAULT_SERVICE,
            names: list[str] | None = None,
        ) -> None:
            self._service_name = service_name
            self._declared_names: list[str] = list(names or [])

        def get(self, name: str) -> str | None:
            assert _keyring is not None  # branch guarded by _KEYRING_AVAILABLE
            assert _keyring_errors is not None  # branch guarded by _KEYRING_AVAILABLE
            try:
                value: str | None = _keyring.get_password(self._service_name, name)
            except _keyring_errors.KeyringError:
                return None
            return value if value else None

        def names(self) -> list[str]:
            return sorted(set(self._declared_names))

else:  # pragma: no cover - exercised by import-side tests when keyring is absent

    class KeyringSecretProvider:  # type: ignore[no-redef]
        """Stub provider raised when the ``keyring`` extra is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            raise ConfigurationError(
                "keyring extra not installed",
            )

        def get(self, name: str) -> str | None:  # pragma: no cover - unreachable
            return None

        def names(self) -> list[str]:  # pragma: no cover - unreachable
            return []


def is_keyring_available() -> bool:
    """Return True iff the ``keyring`` package is importable."""
    return _KEYRING_AVAILABLE


__all__ = ["KeyringSecretProvider", "is_keyring_available"]
