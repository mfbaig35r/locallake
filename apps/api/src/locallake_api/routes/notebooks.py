# SPDX-License-Identifier: Apache-2.0
"""Notebook routes — list, detail, and submit for execution."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun
from locallake_core.notebooks import list_notebooks
from locallake_core.runs import (
    NotebookNotFoundError,
    NotebookPathError,
    resolve_notebook_path,
    submit_job,
)
from locallake_core.templates import (
    InvalidNotebookNameError,
    NotebookAlreadyExistsError,
    TemplateNotFoundError,
    create_from_template,
)
from sqlalchemy import select

from locallake_api.deps import (
    get_config,
    get_marimo_sessions,
    get_redis_pool,
    get_session_factory,
)
from locallake_api.marimo_sessions import (
    MarimoSessionManager,
    MarimoSpawnError,
    PortPoolExhaustedError,
)
from locallake_api.schemas import (
    CreateNotebookRequest,
    JobRunOut,
    MarimoSessionOut,
    NotebookDetailOut,
    NotebookEntryOut,
    NotebookListOut,
    RunNotebookRequest,
)

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.get("", response_model=NotebookListOut)
async def list_notebooks_endpoint(
    cfg: LakehouseConfig = Depends(get_config),
) -> NotebookListOut:
    entries = list_notebooks(cfg)
    items = [
        NotebookEntryOut(
            path=e.path,
            name=e.name,
            size_bytes=e.size_bytes,
            last_modified=e.last_modified,
        )
        for e in entries
    ]
    return NotebookListOut(items=items, total=len(items))


@router.post("", response_model=NotebookEntryOut, status_code=201)
async def create_notebook(
    body: CreateNotebookRequest,
    cfg: LakehouseConfig = Depends(get_config),
) -> NotebookEntryOut:
    try:
        dst = create_from_template(cfg, template=body.template, name=body.name)
    except InvalidNotebookNameError as exc:
        raise HTTPException(400, str(exc)) from exc
    except TemplateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except NotebookAlreadyExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    stat = dst.stat()
    from datetime import datetime

    return NotebookEntryOut(
        path=body.name,
        name=body.name,
        size_bytes=stat.st_size,
        last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def _session_out(sess: Any) -> MarimoSessionOut:
    return MarimoSessionOut(
        notebook_path=sess.notebook_path,
        port=sess.port,
        pid=sess.pid,
        started_at=sess.started_at,
        url=sess.url,
        log_path=sess.log_path,
    )


@router.post(
    "/{notebook_path:path}/edit",
    response_model=MarimoSessionOut,
    status_code=201,
)
async def open_in_marimo(
    notebook_path: str,
    cfg: LakehouseConfig = Depends(get_config),
    sessions: MarimoSessionManager = Depends(get_marimo_sessions),
) -> MarimoSessionOut:
    """Spawn (or reuse) a marimo edit subprocess for ``notebook_path``."""
    try:
        full = resolve_notebook_path(cfg, notebook_path)
    except NotebookPathError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotebookNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        sess = sessions.start(notebook_path, full)
    except PortPoolExhaustedError as exc:
        raise HTTPException(503, str(exc)) from exc
    except MarimoSpawnError as exc:
        raise HTTPException(500, str(exc)) from exc
    return _session_out(sess)


@router.get("/{notebook_path:path}/edit", response_model=MarimoSessionOut | None)
async def get_marimo_session(
    notebook_path: str,
    sessions: MarimoSessionManager = Depends(get_marimo_sessions),
) -> MarimoSessionOut | None:
    sess = sessions.get(notebook_path)
    return _session_out(sess) if sess is not None else None


@router.delete("/{notebook_path:path}/edit", status_code=204)
async def stop_marimo_session(
    notebook_path: str,
    sessions: MarimoSessionManager = Depends(get_marimo_sessions),
) -> None:
    stopped = sessions.stop(notebook_path)
    if not stopped:
        raise HTTPException(404, f"no marimo session for {notebook_path}")


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


# IMPORTANT: this catch-all GET must remain the LAST route registered here.
# Starlette matches in registration order and the ``{notebook_path:path}``
# converter is greedy — earlier specific paths (/edit, /run, …) get swallowed
# if this runs first. See https://github.com/encode/starlette/issues/3025.
@router.get("/{notebook_path:path}", response_model=NotebookDetailOut)
async def get_notebook(
    notebook_path: str,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> NotebookDetailOut:
    try:
        full = resolve_notebook_path(cfg, notebook_path)
    except NotebookPathError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotebookNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    stat = full.stat()
    from datetime import datetime

    session = factory()
    try:
        rows = session.scalars(
            select(JobRun)
            .where(JobRun.notebook_path == notebook_path)
            .order_by(JobRun.created_at.desc())
            .limit(10)
        ).all()
    finally:
        session.close()

    return NotebookDetailOut(
        path=notebook_path,
        name=full.name,
        size_bytes=stat.st_size,
        last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        recent_runs=[JobRunOut.model_validate(r) for r in rows],
    )
