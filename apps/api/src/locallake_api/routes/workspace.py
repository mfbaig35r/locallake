# SPDX-License-Identifier: Apache-2.0
"""Workspace settings — read-only for v1.

Write support (PUT /workspace) is intentionally deferred until we have a
broader plan for hot-reloading config across the API + worker + notebook
subprocess inheritance chain. For now the user edits ``workspace.yaml``
directly and restarts.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from locallake_core.config import LakehouseConfig

from locallake_api.deps import get_config
from locallake_api.schemas import WorkspaceOut, WorkspacePathsOut

router = APIRouter(tags=["workspace"])


@router.get("/workspace", response_model=WorkspaceOut)
async def get_workspace_info(cfg: LakehouseConfig = Depends(get_config)) -> WorkspaceOut:
    from pathlib import Path

    return WorkspaceOut(
        name=cfg.workspace.name,
        root_path=cfg.workspace.root_path,
        database_path=cfg.database.path,
        metadata_db_path=os.environ.get(
            "LOCALLAKE_METADATA_DB",
            str(Path(cfg.database.path).with_name("metadata.sqlite")),
        ),
        paths=WorkspacePathsOut(
            notebooks=cfg.paths.notebooks,
            artifacts=cfg.paths.artifacts,
            logs=cfg.paths.logs,
            templates=cfg.paths.templates,
        ),
        worker_concurrency=int(os.environ.get("LOCALLAKE_WORKER_CONCURRENCY", "2")),
    )
