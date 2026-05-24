# SPDX-License-Identifier: Apache-2.0
"""git_info tests — use a real temp git repo (cheap, no mocks)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from locallake_core.git_info import get_git_info


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def test_returns_none_for_non_repo(tmp_path: Path) -> None:
    sha, dirty = get_git_info(tmp_path)
    assert sha is None
    assert dirty is False


def test_returns_sha_for_clean_repo(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    sha, dirty = get_git_info(tmp_path)
    assert sha is not None
    assert len(sha) == 40
    assert dirty is False


def test_detects_dirty_repo(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    (tmp_path / "f.txt").write_text("y")
    sha, dirty = get_git_info(tmp_path)
    assert sha is not None
    assert dirty is True


def test_missing_path_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    sha, dirty = get_git_info(missing)
    assert sha is None
    assert dirty is False


@pytest.mark.parametrize("path", ["/", "/tmp"])
def test_non_repo_dirs_return_none(path: str) -> None:
    sha, dirty = get_git_info(path)
    assert sha is None
    assert dirty is False
