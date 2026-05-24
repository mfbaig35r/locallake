# SPDX-License-Identifier: Apache-2.0
"""Job routes — list, get, cancel.

``cancel`` is best-effort for Phase 1: queued jobs are marked cancelled and the
arq task — when it eventually fires — sees the row already in a terminal state
and exits. Running jobs cannot yet be killed mid-flight (real subprocess
termination lands in Phase 7 hardening).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from locallake_core.models import JobRun
from sqlalchemy import func, select

from locallake_api.deps import get_session_factory
from locallake_api.schemas import CancelResponse, JobListOut, JobRunOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


_TERMINAL_STATUSES = frozenset({"success", "failed", "cancelled", "timed_out"})


@router.get("", response_model=JobListOut)
async def list_jobs(
    factory: Any = Depends(get_session_factory),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    notebook_path: str | None = Query(default=None),
) -> JobListOut:
    session = factory()
    try:
        count_stmt = select(func.count()).select_from(JobRun)
        list_stmt = select(JobRun).order_by(JobRun.created_at.desc())
        if status:
            count_stmt = count_stmt.where(JobRun.status == status)
            list_stmt = list_stmt.where(JobRun.status == status)
        if notebook_path:
            count_stmt = count_stmt.where(JobRun.notebook_path == notebook_path)
            list_stmt = list_stmt.where(JobRun.notebook_path == notebook_path)
        total = session.scalar(count_stmt) or 0
        rows = session.scalars(list_stmt.limit(limit).offset(offset)).all()
    finally:
        session.close()
    return JobListOut(
        items=[JobRunOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobRunOut)
async def get_job(
    job_id: str,
    factory: Any = Depends(get_session_factory),
) -> JobRunOut:
    session = factory()
    try:
        run = session.get(JobRun, job_id)
    finally:
        session.close()
    if run is None:
        raise HTTPException(404, f"job not found: {job_id}")
    return JobRunOut.model_validate(run)


@router.post("/{job_id}/cancel", response_model=CancelResponse)
async def cancel_job(
    job_id: str,
    factory: Any = Depends(get_session_factory),
) -> CancelResponse:
    session = factory()
    try:
        run = session.get(JobRun, job_id)
        if run is None:
            raise HTTPException(404, f"job not found: {job_id}")
        if run.status in _TERMINAL_STATUSES:
            return CancelResponse(
                id=run.id,
                status=run.status,
                message=f"already {run.status}",
            )
        if run.status == "running":
            raise HTTPException(
                status_code=409,
                detail="cancel during execution not supported in Phase 1",
            )
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        run.error_message = "cancelled by user before execution"
        session.commit()
        return CancelResponse(id=run.id, status=run.status, message="cancelled")
    finally:
        session.close()
