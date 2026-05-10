"""Pytest configuration for golden-file tests.

Adds a single CLI flag::

    pytest tests/golden --update-golden

When set, golden tests overwrite the checked-in expectation files with
the current generator output and mark themselves :func:`xfail` so the
update run is *not* mistaken for a passing run. Without the flag the
default behaviour is byte-strict comparison against the committed
fixtures.

The fixture exposes the option as a boolean ``update_golden`` so test
modules can write::

    def test_x(update_golden: bool) -> None:
        ...
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--update-golden`` CLI flag."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help=(
            "Overwrite the golden expectation files with the current "
            "generator output. The corresponding tests are marked xfail "
            "so the run does not silently pass on a fixture rewrite."
        ),
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Return whether ``--update-golden`` was passed on the CLI."""
    value = request.config.getoption("--update-golden")
    return bool(value)
