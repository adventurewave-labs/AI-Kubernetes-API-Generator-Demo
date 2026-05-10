"""Exit-code mapping tests for the ``generate`` command.

Every row in ``docs/ddd/bounded-contexts/05-user-interaction.md`` §7 is
reproduced as a parametrised case here. The fake orchestrator is
configured to raise the typed error and we assert the CLI's exit code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ai_platform_generator.adapters.cli.main import main
from ai_platform_generator.domain.errors import (
    ArtifactGenerationError,
    ClusterProvisioningError,
    ConfigurationError,
    DomainValidationError,
    IntentInterpretationError,
    PersistenceError,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from click.testing import CliRunner

    from .conftest import _FakeOrchestrator


_INTENT = "Create a VectorDB API"


@pytest.mark.parametrize(
    ("error_factory", "expected_code"),
    [
        pytest.param(
            lambda: IntentInterpretationError("bad intent"),
            10,
            id="intent",
        ),
        pytest.param(
            lambda: DomainValidationError("invalid request"),
            11,
            id="domain-validation",
        ),
        pytest.param(
            lambda: ArtifactGenerationError("template failed"),
            12,
            id="artifact",
        ),
        pytest.param(
            lambda: PersistenceError("disk full"),
            13,
            id="persistence",
        ),
        pytest.param(
            lambda: ClusterProvisioningError("kind missing"),
            14,
            id="cluster",
        ),
        pytest.param(
            lambda: ConfigurationError("missing api key"),
            15,
            id="configuration",
        ),
    ],
)
def test_typed_error_maps_to_exit_code(
    cli_runner: CliRunner,
    fake_orchestrator: _FakeOrchestrator,
    error_factory,
    expected_code: int,
) -> None:
    """Each typed error from §7 surfaces as its documented exit code."""
    fake_orchestrator.will_raise(error_factory())

    result = cli_runner.invoke(
        main,
        ["--no-deploy", "--log-format=json", "generate", _INTENT],
        catch_exceptions=True,
    )

    assert result.exit_code == expected_code, (
        f"expected {expected_code}, got {result.exit_code}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_keyboard_interrupt_maps_to_130(
    cli_runner: CliRunner,
    fake_orchestrator: _FakeOrchestrator,
) -> None:
    """Ctrl-C propagates as the conventional ``130`` exit code."""
    fake_orchestrator.will_raise(KeyboardInterrupt())

    result = cli_runner.invoke(
        main,
        ["--no-deploy", "--log-format=json", "generate", _INTENT],
        catch_exceptions=True,
    )

    assert result.exit_code == 130, (
        f"expected 130, got {result.exit_code}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
