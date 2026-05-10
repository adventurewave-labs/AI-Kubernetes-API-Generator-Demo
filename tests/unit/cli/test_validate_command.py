"""Tests for ``main validate <request-file>``.

The command takes a JSON :class:`CodegenRequest` payload and runs the
domain-validation pipeline (ADR-0016) against it. A clean payload exits
``0``; a payload with violations exits ``11``
(``EXIT_DOMAIN_VALIDATION``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from ai_platform_generator.adapters.cli.main import main

if TYPE_CHECKING:  # pragma: no cover
    from click.testing import CliRunner


def _make_valid_request_payload() -> dict:
    """Return a minimal-but-valid :class:`CodegenRequest` JSON payload."""
    return {
        "gvk": {
            "group": "ai.platform.cnoe.io",
            "version": "v1alpha1",
            "kind": "VectorDB",
        },
        "spec_properties": [
            {
                "name": "engineType",
                "type": "string",
                "description": "Backing vector engine.",
                "constraints": {},
            },
            {
                "name": "replicas",
                "type": "integer",
                "description": "Number of replicas.",
                "constraints": {"minimum": 1, "maximum": 10},
            },
        ],
        "output_path": {
            "root": str(Path.cwd().resolve()),
            "relative": "generated/vector-db",
        },
        "description": "A vector database for AI workloads.",
        "provider_mode": "demo",
    }


def test_validate_valid_request_exits_zero(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """A well-formed request produces exit 0 and a success marker."""
    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps(_make_valid_request_payload()))

    result = cli_runner.invoke(main, ["validate", str(payload_path)])

    assert result.exit_code == 0, result.stderr or result.stdout
    combined = result.stdout + result.stderr
    # Accept either the documented "✓ valid" or any clear success marker.
    assert any(
        marker in combined for marker in ("✓ valid", "valid", "OK", "✅")
    ), f"no success marker in output: {combined!r}"


def test_validate_invalid_request_exits_eleven(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """A payload missing ``kind`` is reported as a domain-validation failure."""
    payload = _make_valid_request_payload()
    # Drop the GVK kind to simulate a missing-required-field violation.
    del payload["gvk"]["kind"]

    payload_path = tmp_path / "request-bad.json"
    payload_path.write_text(json.dumps(payload))

    result = cli_runner.invoke(main, ["validate", str(payload_path)])

    assert result.exit_code == 11, (
        f"expected 11, got {result.exit_code}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # Some violation surface should appear in stderr or stdout — we
    # don't pin the exact wording (Agent P chooses the renderer copy)
    # but at least one identifying token must be present.
    combined = (result.stdout + result.stderr).lower()
    assert any(
        token in combined
        for token in ("kind", "violat", "invalid", "error")
    ), f"no violation marker in output: {result.stderr!r}"
