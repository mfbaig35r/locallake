# SPDX-License-Identifier: Apache-2.0
"""git_info tests — use a real temp git repo (cheap, no mocks)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from locallake_core.git_info import get_git_info, get_git_log, get_git_status


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


def test_git_status_for_non_repo_returns_false(tmp_path: Path) -> None:
    status = get_git_status(tmp_path)
    assert status.is_repo is False
    assert status.branch is None
    assert status.dirty is False


def test_git_status_reports_branch_and_dirty(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    status = get_git_status(tmp_path)
    assert status.is_repo is True
    assert status.branch == "main"
    assert status.dirty is False

    (tmp_path / "f.txt").write_text("y")
    status = get_git_status(tmp_path)
    assert status.dirty is True


def test_git_log_returns_recent_commits(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("1")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "first"], cwd=tmp_path, check=True)
    (tmp_path / "b.txt").write_text("2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=tmp_path, check=True)

    commits = get_git_log(tmp_path, limit=10)
    assert len(commits) == 2
    assert commits[0].message == "second"
    assert commits[1].message == "first"
    assert len(commits[0].sha) == 40
    assert len(commits[0].short_sha) >= 7


def test_git_log_empty_for_non_repo(tmp_path: Path) -> None:
    assert get_git_log(tmp_path) == []
