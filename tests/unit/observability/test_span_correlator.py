"""Tests for :class:`SpanCorrelator`."""

from __future__ import annotations

import pytest

from ai_platform_generator.domain.observability.span_correlator import SpanCorrelator


class TestOpenClose:
    def test_open_returns_unique_ids(self) -> None:
        sc = SpanCorrelator()
        a = sc.open("run-1", "stage:interpret")
        b = sc.open("run-1", "stage:model")
        assert a != b
        assert sc.current("run-1") == b

    def test_close_pops_top(self) -> None:
        sc = SpanCorrelator()
        a = sc.open("run-1", "root")
        b = sc.open("run-1", "child")
        sc.close("run-1", b)
        assert sc.current("run-1") == a

    def test_close_full_stack_clears_current(self) -> None:
        sc = SpanCorrelator()
        a = sc.open("run-1", "root")
        sc.close("run-1", a)
        assert sc.current("run-1") is None


class TestIsolation:
    def test_runs_are_independent(self) -> None:
        sc = SpanCorrelator()
        a = sc.open("run-1", "root")
        b = sc.open("run-2", "root")
        assert sc.current("run-1") == a
        assert sc.current("run-2") == b
        sc.close("run-1", a)
        # run-2 still has its own active span.
        assert sc.current("run-2") == b

    def test_run_id_coerced_to_string(self) -> None:
        sc = SpanCorrelator()
        a = sc.open(123, "root")  # type: ignore[arg-type]
        assert sc.current("123") == a


class TestIllegalPop:
    def test_close_empty_stack_raises(self) -> None:
        sc = SpanCorrelator()
        with pytest.raises(AssertionError, match="empty"):
            sc.close("run-1", "deadbeef")

    def test_close_wrong_id_raises_and_keeps_state(self) -> None:
        sc = SpanCorrelator()
        a = sc.open("run-1", "root")
        with pytest.raises(AssertionError, match="closing span"):
            sc.close("run-1", "wrong-id")
        # Stack must still be intact so the caller can recover.
        assert sc.current("run-1") == a

    def test_current_unknown_run(self) -> None:
        sc = SpanCorrelator()
        assert sc.current("never-opened") is None
