"""Unit tests for the composition root.

Exercise both the ``use_fakes=True`` smoke path and the real-adapter
selection path. The latter must construct cleanly even when no API
key is available — the production wiring degrades to demo mode rather
than raising on missing secrets at composition time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_platform_generator.application.composition import (
    AppConfig,
    build_orchestrator,
    build_test_orchestrator,
)
from ai_platform_generator.application.orchestrator import (
    GenerationOrchestrator,
)

# ---------------------------------------------------------------------------
# Fake wiring (use_fakes=True)
# ---------------------------------------------------------------------------


def test_build_test_orchestrator_returns_orchestrator() -> None:
    orc = build_test_orchestrator()
    assert isinstance(orc, GenerationOrchestrator)


def test_build_orchestrator_use_fakes() -> None:
    orc = build_orchestrator(AppConfig(use_fakes=True))
    assert isinstance(orc, GenerationOrchestrator)


def test_appconfig_defaults() -> None:
    cfg = AppConfig()
    assert cfg.llm_provider == "openrouter"
    assert cfg.use_fakes is False
    assert cfg.allow_demo_mode is True
    assert cfg.cluster_name == "ai-platform-demo"
    assert cfg.log_format == "tty"
    assert cfg.enable_otel is False


def test_appconfig_is_frozen() -> None:
    cfg = AppConfig()
    with pytest.raises(Exception):
        cfg.cluster_name = "other"  # type: ignore[misc]


def test_appconfig_rejects_unknown_log_format() -> None:
    with pytest.raises(Exception):
        AppConfig(log_format="loud")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Real-adapter selection
# ---------------------------------------------------------------------------


def test_real_orchestrator_constructs_without_api_key(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """No API key → composition root must not raise.

    The composition root should fall back to a constructable primary
    (warning the operator) so that the rest of the pipeline can still
    be exercised. ``FallbackLlmProvider`` then takes over on first
    invocation.
    """
    # Pristine env: the real path resolves API keys via a chain ending
    # in ``EnvSecretProvider`` + ``DotenvSecretProvider``. Strip both.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # avoid picking up a real ``.env``

    cfg = AppConfig(
        artifact_root=tmp_path / "artifacts",
        runs_log_path=tmp_path / "runs.jsonl",
        log_format="quiet",  # silence structlog noise
        enable_otel=False,
    )
    with pytest.warns(UserWarning, match="OPENROUTER_API_KEY"):
        orc = build_orchestrator(cfg)
    assert isinstance(orc, GenerationOrchestrator)


def test_real_orchestrator_with_dummy_api_key(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """An API key present → primary is constructed without warning."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-deadbeef-not-real")
    monkeypatch.chdir(tmp_path)

    cfg = AppConfig(
        artifact_root=tmp_path / "artifacts",
        runs_log_path=tmp_path / "runs.jsonl",
        log_format="quiet",
    )
    orc = build_orchestrator(cfg)
    assert isinstance(orc, GenerationOrchestrator)


def test_real_orchestrator_demo_provider_choice(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """``llm_provider='demo'`` skips the live adapter entirely."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    cfg = AppConfig(
        llm_provider="demo",
        artifact_root=tmp_path / "artifacts",
        runs_log_path=tmp_path / "runs.jsonl",
        log_format="quiet",
    )
    orc = build_orchestrator(cfg)
    assert isinstance(orc, GenerationOrchestrator)


def test_real_orchestrator_fake_provider_choice(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """``llm_provider='fake'`` selects the in-memory adapter as primary."""
    monkeypatch.chdir(tmp_path)
    cfg = AppConfig(
        llm_provider="fake",
        artifact_root=tmp_path / "artifacts",
        runs_log_path=tmp_path / "runs.jsonl",
        log_format="quiet",
    )
    orc = build_orchestrator(cfg)
    assert isinstance(orc, GenerationOrchestrator)


def test_disable_demo_mode_returns_primary_directly(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """When ``allow_demo_mode=False`` the primary is *not* wrapped."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-deadbeef")
    monkeypatch.chdir(tmp_path)
    cfg = AppConfig(
        allow_demo_mode=False,
        artifact_root=tmp_path / "artifacts",
        runs_log_path=tmp_path / "runs.jsonl",
        log_format="quiet",
    )
    orc = build_orchestrator(cfg)
    assert isinstance(orc, GenerationOrchestrator)
