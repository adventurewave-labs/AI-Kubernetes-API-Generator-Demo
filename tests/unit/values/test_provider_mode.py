"""Tests for ``ai_platform_generator.domain.values.provider_mode``."""

from __future__ import annotations

from ai_platform_generator.domain.values.provider_mode import ProviderMode


def test_values() -> None:
    assert ProviderMode.LIVE.value == "live"
    assert ProviderMode.DEMO.value == "demo"


def test_strenum_compat() -> None:
    assert ProviderMode.LIVE == "live"
    assert "demo" == ProviderMode.DEMO


def test_iteration() -> None:
    assert {m.name for m in ProviderMode} == {"LIVE", "DEMO"}
