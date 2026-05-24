# SPDX-License-Identifier: Apache-2.0
"""Schedule CRUD — cron-driven notebook runs.

Schedules are evaluated by the worker's in-process scheduler (see
``locallake_worker.scheduler``). Edits take effect on the worker's next
tick (≤60s), no restart needed.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from locallake_core.config import LakehouseConfig
from locallake_core.cron import InvalidCronError, next_fire, validate
from locallake_core.models import Schedule
from locallake_core.runs import (
    NotebookNotFoundError,
    NotebookPathError,
    resolve_notebook_path,
)
from sqlalchemy import select

from locallake_api.deps import get_config, get_session_factory
from locallake_api.schemas import (
    ScheduleIn,
    ScheduleListOut,
    ScheduleOut,
    ScheduleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _serialize(s: Schedule) -> ScheduleOut:
    try:
        upcoming = next_fire(s.cron_expression) if s.enabled else None
    except Exception:
        upcoming = None
    return ScheduleOut(
        id=s.id,
        notebook_path=s.notebook_path,
        cron_expression=s.cron_expression,
        enabled=s.enabled,
        last_run_at=s.last_run_at,
        last_run_id=s.last_run_id,
        created_at=s.created_at,
        parameters_json=s.parameters_json,
        next_fire_at=upcoming,
        max_retries=s.max_retries,
    )


@router.get("", response_model=ScheduleListOut)
async def list_schedules(
    factory: Any = Depends(get_session_factory),
) -> ScheduleListOut:
    session = factory()
    try:
        rows = session.scalars(select(Schedule).order_by(Schedule.created_at.desc())).all()
    finally:
        session.close()
    return ScheduleListOut(items=[_serialize(r) for r in rows], total=len(rows))


@router.post("", response_model=ScheduleOut, status_code=201)
async def create_schedule(
    body: ScheduleIn,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> ScheduleOut:
    try:
        validate(body.cron_expression)
    except InvalidCronError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Validate notebook exists at create time. Edits to the notebook later
    # are the user's problem — the worker logs a failure if it goes missing.
    try:
        resolve_notebook_path(cfg, body.notebook_path)
    except NotebookPathError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotebookNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    session = factory()
    try:
        sched = Schedule(
            notebook_path=body.notebook_path,
            cron_expression=body.cron_expression,
            enabled=body.enabled,
            created_at=datetime.now(UTC),
            parameters_json=json.dumps(body.parameters),
            max_retries=body.max_retries,
        )
        session.add(sched)
        session.commit()
        session.refresh(sched)
        return _serialize(sched)
    finally:
        session.close()


@router.patch("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    factory: Any = Depends(get_session_factory),
) -> ScheduleOut:
    session = factory()
    try:
        sched = session.get(Schedule, schedule_id)
        if sched is None:
            raise HTTPException(404, f"schedule not found: {schedule_id}")
        if body.cron_expression is not None:
            try:
                validate(body.cron_expression)
            except InvalidCronError as exc:
                raise HTTPException(400, str(exc)) from exc
            sched.cron_expression = body.cron_expression
        if body.enabled is not None:
            sched.enabled = body.enabled
        if body.parameters is not None:
            sched.parameters_json = json.dumps(body.parameters)
        if body.max_retries is not None:
            sched.max_retries = body.max_retries
        session.commit()
        session.refresh(sched)
        return _serialize(sched)
    finally:
        session.close()


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    factory: Any = Depends(get_session_factory),
) -> None:
    session = factory()
    try:
        sched = session.get(Schedule, schedule_id)
        if sched is None:
            raise HTTPException(404, f"schedule not found: {schedule_id}")
        session.delete(sched)
        session.commit()
    finally:
        session.close()
