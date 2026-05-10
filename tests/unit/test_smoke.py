"""Phase 0 smoke test: package imports and exposes its version."""

import ai_platform_generator


def test_package_version() -> None:
    assert ai_platform_generator.__version__ == "0.1.0"
