"""Tests for :class:`FrozenClock`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai_platform_generator.adapters.clock.frozen import FrozenClock


def test_default_initial_is_utc_aware() -> None:
    clock = FrozenClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_now_is_frozen_until_advance() -> None:
    initial = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    clock = FrozenClock(initial=initial)

    assert clock.now() == initial
    assert clock.now() == initial  # truly frozen


def test_advance_moves_now_and_monotonic() -> None:
    initial = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    clock = FrozenClock(initial=initial)

    start_monotonic = clock.monotonic()
    clock.advance(timedelta(seconds=30))

    assert clock.now() == initial + timedelta(seconds=30)
    assert clock.monotonic() == pytest.approx(start_monotonic + 30.0)


def test_advance_accumulates() -> None:
    clock = FrozenClock(initial=datetime(2024, 1, 1, tzinfo=timezone.utc))
    clock.advance(timedelta(seconds=1))
    clock.advance(timedelta(seconds=2))
    clock.advance(timedelta(seconds=3))
    assert clock.monotonic() == pytest.approx(6.0)


def test_advance_negative_rejected() -> None:
    clock = FrozenClock()
    with pytest.raises(ValueError, match="cannot move backwards"):
        clock.advance(timedelta(seconds=-1))


def test_naive_initial_is_promoted_to_utc() -> None:
    naive = datetime(2024, 6, 1, 12, 0)
    clock = FrozenClock(initial=naive)
    assert clock.now().tzinfo == timezone.utc
