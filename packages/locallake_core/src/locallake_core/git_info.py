# SPDX-License-Identifier: Apache-2.0
"""Git introspection — capture commit SHA + dirty status at job submission.

All git commands run with fixed argv and ``shell=False``. If git isn't
installed, the repo isn't initialized, or anything else goes wrong, we return
``(None, False)`` rather than raising — git info is metadata, not load-bearing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 5


@dataclass
class GitStatus:
    is_repo: bool
    branch: str | None
    commit_sha: str | None
    dirty: bool
    ahead: int
    behind: int


@dataclass
class GitCommit:
    sha: str
    short_sha: str
    author: str
    date: datetime
    message: str


def get_git_info(repo_path: str | Path) -> tuple[str | None, bool]:
    """Return ``(commit_sha, dirty)`` for the repo at ``repo_path``.

    Returns ``(None, False)`` if the path isn't a git repo, git is unavailable,
    or any subprocess fails. Both calls have a 5s timeout.
    """
    repo = str(repo_path)
    try:
        sha_proc = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None, False
    if sha_proc.returncode != 0:
        return None, False
    commit = sha_proc.stdout.strip()

    try:
        status_proc = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return commit, False
    dirty = bool(status_proc.stdout.strip()) if status_proc.returncode == 0 else False
    return commit, dirty


def _git(
    repo: str, *args: str, timeout: int = _GIT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str] | None:
    """Run ``git -C repo <args>``; return None on any subprocess failure."""
    try:
        return subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def get_git_status(repo_path: str | Path) -> GitStatus:
    """Return ``GitStatus`` for ``repo_path``; ``is_repo=False`` if not a repo."""
    repo = str(repo_path)
    head = _git(repo, "rev-parse", "HEAD")
    if head is None or head.returncode != 0:
        return GitStatus(
            is_repo=False,
            branch=None,
            commit_sha=None,
            dirty=False,
            ahead=0,
            behind=0,
        )
    sha = head.stdout.strip()

    branch_proc = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_proc.stdout.strip() if branch_proc and branch_proc.returncode == 0 else None

    status_proc = _git(repo, "status", "--porcelain")
    dirty = bool(status_proc.stdout.strip() if status_proc and status_proc.returncode == 0 else "")

    ahead, behind = 0, 0
    ab_proc = _git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if ab_proc and ab_proc.returncode == 0:
        parts = ab_proc.stdout.strip().split()
        if len(parts) == 2:
            try:
                behind = int(parts[0])
                ahead = int(parts[1])
            except ValueError:
                pass

    return GitStatus(
        is_repo=True,
        branch=branch,
        commit_sha=sha,
        dirty=dirty,
        ahead=ahead,
        behind=behind,
    )


def get_git_log(repo_path: str | Path, limit: int = 20) -> list[GitCommit]:
    """Return up to ``limit`` recent commits, newest first. Empty on non-repo."""
    if limit < 1 or limit > 200:
        raise ValueError("limit must be between 1 and 200")
    repo = str(repo_path)
    # Field separator chosen to be unlikely in commit metadata.
    sep = "\x1f"
    log_proc = _git(
        repo,
        "log",
        f"-n{limit}",
        f"--pretty=format:%H{sep}%h{sep}%an{sep}%aI{sep}%s",
    )
    if log_proc is None or log_proc.returncode != 0:
        return []
    commits: list[GitCommit] = []
    for line in log_proc.stdout.splitlines():
        parts = line.split(sep, 4)
        if len(parts) != 5:
            continue
        sha, short_sha, author, iso, message = parts
        try:
            date = datetime.fromisoformat(iso)
        except ValueError:
            date = datetime.now(UTC)
        commits.append(
            GitCommit(
                sha=sha,
                short_sha=short_sha,
                author=author,
                date=date,
                message=message,
            )
        )
    return commits
