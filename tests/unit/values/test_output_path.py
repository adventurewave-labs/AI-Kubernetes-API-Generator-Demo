"""Tests for ``ai_platform_generator.domain.values.output_path``."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_platform_generator.domain.errors import InvalidOutputPath
from ai_platform_generator.domain.values.output_path import OutputPath


def test_simple_relative_resolves_inside_root(tmp_path: Path) -> None:
    op = OutputPath(root=tmp_path, relative=Path("sub/file.yaml"))
    assert op.full == (tmp_path / "sub/file.yaml").resolve()
    # tmp_path is already absolute on every platform we care about.
    assert op.root == tmp_path.resolve()


def test_root_is_resolved_to_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    rel_root = Path(".")
    op = OutputPath(root=rel_root, relative=Path("file.txt"))
    assert op.root.is_absolute()


def test_dotdot_in_relative_rejects(tmp_path: Path) -> None:
    with pytest.raises(InvalidOutputPath):
        OutputPath(root=tmp_path, relative=Path("../escape"))


def test_nested_dotdot_rejects(tmp_path: Path) -> None:
    with pytest.raises(InvalidOutputPath):
        OutputPath(root=tmp_path, relative=Path("a/../../escape"))


def test_absolute_relative_rejects(tmp_path: Path) -> None:
    with pytest.raises(InvalidOutputPath):
        OutputPath(root=tmp_path, relative=Path("/etc/passwd"))


def test_root_equal_full_when_relative_is_dot(tmp_path: Path) -> None:
    op = OutputPath(root=tmp_path, relative=Path("."))
    assert op.full == tmp_path.resolve()


def test_non_path_root_rejects(tmp_path: Path) -> None:
    with pytest.raises(InvalidOutputPath):
        OutputPath(root=str(tmp_path), relative=Path("a"))  # type: ignore[arg-type]


def test_non_path_relative_rejects(tmp_path: Path) -> None:
    with pytest.raises(InvalidOutputPath):
        OutputPath(root=tmp_path, relative="a")  # type: ignore[arg-type]


def test_equality_and_hash(tmp_path: Path) -> None:
    a = OutputPath(root=tmp_path, relative=Path("x"))
    b = OutputPath(root=tmp_path, relative=Path("x"))
    c = OutputPath(root=tmp_path, relative=Path("y"))
    assert a == b
    assert a != c
    assert len({a, b, c}) == 2
