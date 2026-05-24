# SPDX-License-Identifier: Apache-2.0
"""SQL routes — read-only query execution + saved queries + history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from locallake_core.config import LakehouseConfig
from locallake_core.models import QueryHistory, SavedQuery
from locallake_core.sql import (
    SqlTimeoutError,
    SqlValidationError,
    run_query,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from locallake_api.deps import get_config, get_session_factory
from locallake_api.schemas import (
    QueryHistoryListOut,
    QueryHistoryOut,
    QueryRequest,
    QueryResultOut,
    SavedQueryIn,
    SavedQueryListOut,
    SavedQueryOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql", tags=["sql"])


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _record_history(
    factory: Any,
    *,
    sql: str,
    duration_ms: int,
    row_count: int | None,
    error_message: str | None,
) -> None:
    session = factory()
    try:
        session.add(
            QueryHistory(
                sql=sql,
                executed_at=_utc_now(),
                duration_ms=duration_ms,
                row_count=row_count,
                error_message=error_message,
            )
        )
        session.commit()
    finally:
        session.close()


@router.post("/query", response_model=QueryResultOut)
async def query(
    body: QueryRequest,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> QueryResultOut:
    try:
        result = run_query(
            cfg.database.path,
            body.sql,
            row_limit=body.row_limit,
            timeout_seconds=body.timeout_seconds,
        )
    except SqlValidationError as exc:
        _record_history(
            factory,
            sql=body.sql,
            duration_ms=0,
            row_count=None,
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SqlTimeoutError as exc:
        _record_history(
            factory,
            sql=body.sql,
            duration_ms=body.timeout_seconds * 1000,
            row_count=None,
            error_message=str(exc),
        )
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except Exception as exc:
        _record_history(
            factory,
            sql=body.sql,
            duration_ms=0,
            row_count=None,
            error_message=str(exc),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _record_history(
        factory,
        sql=body.sql,
        duration_ms=result.duration_ms,
        row_count=result.row_count,
        error_message=None,
    )
    return QueryResultOut(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        duration_ms=result.duration_ms,
    )


@router.get("/saved", response_model=SavedQueryListOut)
async def list_saved(
    factory: Any = Depends(get_session_factory),
) -> SavedQueryListOut:
    session = factory()
    try:
        rows = session.scalars(select(SavedQuery).order_by(SavedQuery.name)).all()
    finally:
        session.close()
    return SavedQueryListOut(
        items=[SavedQueryOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/saved", response_model=SavedQueryOut, status_code=201)
async def create_saved(
    body: SavedQueryIn,
    factory: Any = Depends(get_session_factory),
) -> SavedQueryOut:
    session = factory()
    try:
        sq = SavedQuery(name=body.name, sql=body.sql)
        session.add(sq)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, f"name already exists: {body.name!r}") from exc
        session.refresh(sq)
        return SavedQueryOut.model_validate(sq)
    finally:
        session.close()


@router.delete("/saved/{saved_id}", status_code=204)
async def delete_saved(
    saved_id: str,
    factory: Any = Depends(get_session_factory),
) -> None:
    session = factory()
    try:
        sq = session.get(SavedQuery, saved_id)
        if sq is None:
            raise HTTPException(404, f"saved query not found: {saved_id}")
        session.delete(sq)
        session.commit()
    finally:
        session.close()


@router.get("/history", response_model=QueryHistoryListOut)
async def list_history(
    factory: Any = Depends(get_session_factory),
    limit: int = Query(default=50, ge=1, le=200),
) -> QueryHistoryListOut:
    session = factory()
    try:
        total = session.scalar(select(func.count()).select_from(QueryHistory)) or 0
        rows = session.scalars(
            select(QueryHistory).order_by(QueryHistory.executed_at.desc()).limit(limit)
        ).all()
    finally:
        session.close()
    return QueryHistoryListOut(
        items=[QueryHistoryOut.model_validate(r) for r in rows],
        total=total,
    )
