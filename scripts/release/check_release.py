"""Release-time guard for ai-platform-generator.

Asserts the repo is in a publishable state before tagging / pushing:

  1. The current commit is tagged.
  2. The tag matches the version in ``pyproject.toml`` (read via ``tomllib``).
     The version itself is read from ``src/ai_platform_generator/__init__.py``
     because ``pyproject.toml`` declares ``dynamic = ["version"]`` and points
     ``[tool.hatch.version] path`` at that file.
  3. ``CHANGELOG.md`` has a section for the version that is being released.
  4. The working tree is clean (no uncommitted changes).

Used both by the release workflow and as a local pre-tag check::

    python scripts/release/check_release.py            # current HEAD
    python scripts/release/check_release.py --tag v1.2.3
    python scripts/release/check_release.py --extract-notes \\
        --tag v1.2.3 --output release_notes.md

The ``--extract-notes`` mode prints (or writes) the CHANGELOG section for the
tag, suitable for use as the body of a GitHub Release.

Stdlib-only by design — must run before any project deps are installed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PACKAGE_INIT = REPO_ROOT / "src" / "ai_platform_generator" / "__init__.py"

VERSION_RE = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


class ReleaseCheckError(RuntimeError):
    """Raised when one of the release-time invariants fails."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(*args: str) -> str:
    """Run ``git <args>`` from the repo root and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def read_pyproject_version() -> str:
    """Resolve the project version.

    ``pyproject.toml`` declares ``dynamic = ["version"]`` with hatch sourcing
    the version from ``src/ai_platform_generator/__init__.py``. We replicate
    that resolution here without depending on hatch.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})
    if "version" in project:
        return str(project["version"])

    hatch_version = (
        data.get("tool", {}).get("hatch", {}).get("version", {}).get("path")
    )
    version_path = (
        REPO_ROOT / hatch_version if hatch_version else PACKAGE_INIT
    )
    text = version_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise ReleaseCheckError(
            f"Could not find __version__ in {version_path}"
        )
    return match.group(1)


def current_tag() -> str | None:
    """Return the tag pointing at HEAD, or ``None`` if HEAD isn't tagged."""
    try:
        tag = _run_git("describe", "--tags", "--exact-match", "HEAD")
    except subprocess.CalledProcessError:
        return None
    return tag or None


def working_tree_is_clean() -> bool:
    status = _run_git("status", "--porcelain")
    return status == ""


def _normalise_tag(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def changelog_section(version: str) -> str | None:
    """Return the CHANGELOG section body for ``version``, or ``None``.

    A section header is matched as ``## [<version>]`` (Keep a Changelog 1.1.0
    style). The returned body excludes the header line and stops at the next
    ``## `` heading.
    """
    if not CHANGELOG.exists():
        return None
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^##\s*\[" + re.escape(version) + r"\][^\n]*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def assert_release(expected_tag: str | None = None) -> str:
    """Run all release-time checks. Returns the resolved tag on success."""
    errors: list[str] = []

    head_tag = current_tag()
    tag = expected_tag or head_tag

    if expected_tag is None and head_tag is None:
        errors.append("HEAD is not tagged (no annotated/lightweight tag).")
    elif expected_tag is not None and head_tag is not None and expected_tag != head_tag:
        errors.append(
            f"HEAD is tagged {head_tag!r} but expected {expected_tag!r}."
        )

    if tag is None:
        # Cannot proceed with version comparison if we don't know the tag.
        raise ReleaseCheckError("\n".join(errors))

    version = read_pyproject_version()
    tag_version = _normalise_tag(tag)
    if tag_version != version:
        errors.append(
            f"Tag {tag!r} does not match pyproject version {version!r}."
        )

    if changelog_section(version) is None:
        errors.append(
            f"CHANGELOG.md has no section for version {version!r}. "
            f"Add a '## [{version}]' heading."
        )

    if not working_tree_is_clean():
        errors.append(
            "Working tree is dirty (uncommitted changes). "
            "Commit or stash before releasing."
        )

    if errors:
        raise ReleaseCheckError("\n".join(f"- {e}" for e in errors))
    return tag


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Release-time guard for ai-platform-generator.",
    )
    parser.add_argument(
        "--tag",
        help=(
            "Expected git tag (e.g. v1.2.3). "
            "If omitted, the tag at HEAD is used."
        ),
    )
    parser.add_argument(
        "--extract-notes",
        action="store_true",
        help=(
            "Instead of running the full release check, print the "
            "CHANGELOG section body for the resolved version."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file to write the extracted notes to.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.extract_notes:
        tag = args.tag or current_tag()
        if tag is None:
            print("error: no tag provided and HEAD is not tagged", file=sys.stderr)
            return 2
        version = _normalise_tag(tag)
        body = changelog_section(version)
        if body is None:
            print(
                f"error: CHANGELOG.md has no section for {version}",
                file=sys.stderr,
            )
            return 3
        if args.output:
            args.output.write_text(body + "\n", encoding="utf-8")
        else:
            print(body)
        return 0

    try:
        tag = assert_release(args.tag)
    except ReleaseCheckError as exc:
        print("Release check failed:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Release check passed for {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
