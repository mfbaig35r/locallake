# SPDX-License-Identifier: Apache-2.0
"""Git introspection — capture commit SHA + dirty status at job submission.

All git commands run with fixed argv and ``shell=False``. If git isn't
installed, the repo isn't initialized, or anything else goes wrong, we return
``(None, False)`` rather than raising — git info is metadata, not load-bearing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 5


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
