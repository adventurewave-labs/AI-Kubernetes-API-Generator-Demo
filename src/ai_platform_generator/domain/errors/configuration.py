"""Configuration / prerequisite errors.

These errors are raised before any meaningful work has been done — usually
during CLI startup or in the very first stage of a Generation Run.
"""
from __future__ import annotations

from typing import Any

from .base import PlatformGeneratorError


class ConfigurationError(PlatformGeneratorError):
    """Base class for configuration-time problems."""

    code = "E_CONFIG_GENERIC"


class MissingApiKey(ConfigurationError):
    """No usable API key was found for the configured LLM provider."""

    code = "E_CONFIG_MISSING_API_KEY"

    def __init__(
        self,
        user_message: str = (
            "No API key configured. Set ANTHROPIC_API_KEY (or the equivalent "
            "for your provider) in your environment, or pass --demo to run "
            "without an LLM."
        ),
        *,
        cause: Exception | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(user_message, cause=cause, **extra)


class InvalidConfigFile(ConfigurationError):
    """The on-disk config file is malformed or references unknown keys."""

    code = "E_CONFIG_INVALID_FILE"


class PrerequisiteMissing(ConfigurationError):
    """One or more required external tools (kubectl, kind, docker) are absent.

    Attributes:
        missing_tools: tools that are not on ``$PATH``.
        install_hint:  per-tool installation hint (URL or shell snippet).
    """

    code = "E_CONFIG_PREREQUISITE_MISSING"

    def __init__(
        self,
        missing_tools: list[str],
        install_hint: dict[str, str] | None = None,
        *,
        user_message: str | None = None,
        cause: Exception | None = None,
        **extra: Any,
    ) -> None:
        self.missing_tools: list[str] = list(missing_tools)
        self.install_hint: dict[str, str] = dict(install_hint or {})
        if user_message is None:
            joined = ", ".join(self.missing_tools) or "<none>"
            user_message = (
                f"Required tools not found on PATH: {joined}. "
                "Install them and re-run, or pass --skip-cluster to skip "
                "cluster provisioning."
            )
        super().__init__(user_message, cause=cause, **extra)
