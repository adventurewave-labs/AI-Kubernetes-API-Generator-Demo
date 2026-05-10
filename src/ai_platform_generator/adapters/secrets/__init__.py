"""Secrets adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.secrets.chain import ChainSecretProvider
from ai_platform_generator.adapters.secrets.dotenv import DotenvSecretProvider
from ai_platform_generator.adapters.secrets.env import (
    DEFAULT_NAME_PATTERN,
    EnvSecretProvider,
)
from ai_platform_generator.adapters.secrets.in_memory import InMemorySecretProvider
from ai_platform_generator.adapters.secrets.keyring_provider import (
    KeyringSecretProvider,
    is_keyring_available,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_NAME_PATTERN",
    "ChainSecretProvider",
    "DotenvSecretProvider",
    "EnvSecretProvider",
    "InMemorySecretProvider",
    "KeyringSecretProvider",
    "__version__",
    "is_keyring_available",
]
