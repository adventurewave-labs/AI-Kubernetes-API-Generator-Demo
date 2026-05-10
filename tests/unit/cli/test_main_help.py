"""Smoke-test ``main --help`` and ``main --version``.

Per ``docs/ddd/bounded-contexts/05-user-interaction.md`` §10 the CLI is
part of the public contract; ``--help`` and ``--version`` must always
exit 0 even when the rest of the application stack is degraded
(missing API key, no Kind cluster, etc.).
"""

from __future__ import annotations

from click.testing import CliRunner

from ai_platform_generator.adapters.cli.main import main


def test_main_help_exits_zero(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0, result.stderr
    # The top-level usage banner is part of the contract.
    assert "Usage:" in result.stdout


def test_main_version_exits_zero(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0, result.stderr
    # Click's version-option emits the program name + a version string.
    assert "ai-platform-generator" in result.stdout


def test_no_args_lists_subcommands(cli_runner: CliRunner) -> None:
    """No subcommand means Click prints help and exits 0 (with no error)."""
    result = cli_runner.invoke(main, [])
    # Click's group default behaviour is to exit 0 and print help.
    assert result.exit_code in (0, 2)
    # Either way, the listing of subcommands should appear.
    combined = result.stdout + result.stderr
    for cmd in ("generate", "interactive", "examples", "cluster", "validate"):
        assert cmd in combined
