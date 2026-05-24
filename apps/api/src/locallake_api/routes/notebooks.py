# SPDX-License-Identifier: Apache-2.0
"""Notebook routes — list + submit for execution.

``POST /notebooks/{path:path}/run`` is the Phase 1 demo endpoint:
validate the path, capture git state, insert a JobRun row, enqueue an arq
``run_notebook`` task, return the JobRun.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from locallake_core.config import LakehouseConfig
from locallake_core.runs import (
    NotebookNotFoundError,
    NotebookPathError,
    submit_job,
)

from locallake_api.deps import get_config, get_redis_pool, get_session_factory
from locallake_api.schemas import JobRunOut, RunNotebookRequest

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post(
    "/{notebook_path:path}/run",
    response_model=JobRunOut,
    status_code=202,
)
async def run_notebook(
    notebook_path: str,
    body: RunNotebookRequest | None = None,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
    pool: Any = Depends(get_redis_pool),
) -> JobRunOut:
    body = body or RunNotebookRequest()
    try:
        run = await submit_job(
            cfg,
            factory,
            pool,
            notebook_path=notebook_path,
            parameters=body.parameters,
            triggered_by=body.triggered_by,
            timeout_seconds=body.timeout_seconds,
        )
    except NotebookPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JobRunOut.model_validate(run)
