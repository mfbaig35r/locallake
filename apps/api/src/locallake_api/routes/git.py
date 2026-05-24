# SPDX-License-Identifier: Apache-2.0
"""Git routes — status + log of the workspace repo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from locallake_core.config import LakehouseConfig
from locallake_core.git_info import get_git_log, get_git_status

from locallake_api.deps import get_config
from locallake_api.schemas import GitCommitOut, GitLogOut, GitStatusOut

router = APIRouter(prefix="/git", tags=["git"])


@router.get("/status", response_model=GitStatusOut)
async def status_endpoint(cfg: LakehouseConfig = Depends(get_config)) -> GitStatusOut:
    s = get_git_status(cfg.workspace.root_path)
    return GitStatusOut(
        is_repo=s.is_repo,
        branch=s.branch,
        commit_sha=s.commit_sha,
        dirty=s.dirty,
        ahead=s.ahead,
        behind=s.behind,
    )


@router.get("/log", response_model=GitLogOut)
async def log_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    cfg: LakehouseConfig = Depends(get_config),
) -> GitLogOut:
    commits = get_git_log(cfg.workspace.root_path, limit=limit)
    return GitLogOut(
        items=[
            GitCommitOut(
                sha=c.sha,
                short_sha=c.short_sha,
                author=c.author,
                date=c.date,
                message=c.message,
            )
            for c in commits
        ],
        total=len(commits),
    )
