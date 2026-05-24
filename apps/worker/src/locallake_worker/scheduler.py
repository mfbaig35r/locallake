# SPDX-License-Identifier: Apache-2.0
"""In-process cron loop — one asyncio task that watches the Schedule table.

Why custom and not arq's `cron_jobs`: arq registers cron functions at
``WorkerSettings`` load time, so adding or editing a schedule would require
restarting the worker. This loop re-reads the table on every tick, so
edits made via the API take effect within ``TICK_SECONDS``.

Catch-up policy is delegated to ``locallake_core.cron.is_due``: at most one
fire per schedule per tick. See that module's docstring.

Time is UTC. Per-schedule timezones are a v2 concern.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from locallake_core.config import LakehouseConfig
from locallake_core.cron import is_due
from locallake_core.models import Schedule
from locallake_core.runs import submit_job
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Tick once a minute — matches the resolution of POSIX cron.
TICK_SECONDS = 60.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _tick(
    cfg: LakehouseConfig,
    session_factory: sessionmaker[Session],
    pool: Any,
    now: datetime | None = None,
) -> list[str]:
    """One pass over the schedules table. Returns the list of fired schedule IDs."""
    moment = (now or _utc_now()).astimezone(UTC)
    fired: list[str] = []

    session = session_factory()
    try:
        rows = session.scalars(select(Schedule).where(Schedule.enabled.is_(True))).all()
    finally:
        session.close()

    for row in rows:
        try:
            if not is_due(row.cron_expression, row.last_run_at, moment):
                continue
        except Exception:
            logger.exception("schedule %s has invalid cron %r", row.id, row.cron_expression)
            continue

        try:
            params: dict[str, Any] = json.loads(row.parameters_json or "{}")
        except json.JSONDecodeError:
            logger.warning("schedule %s has invalid parameters_json; using {}", row.id)
            params = {}

        try:
            run = await submit_job(
                cfg,
                session_factory,
                pool,
                notebook_path=row.notebook_path,
                parameters=params,
                triggered_by="schedule",
            )
        except Exception:
            logger.exception("schedule %s: submit_job failed", row.id)
            continue

        session = session_factory()
        try:
            persisted = session.get(Schedule, row.id)
            if persisted is None:
                continue
            persisted.last_run_at = moment
            persisted.last_run_id = run.id
            session.commit()
        finally:
            session.close()

        fired.append(row.id)
        logger.info("schedule %s fired → job %s", row.id, run.id)

    return fired


async def run_loop(
    cfg: LakehouseConfig,
    session_factory: sessionmaker[Session],
    pool: Any,
    tick_seconds: float = TICK_SECONDS,
) -> None:
    """Forever loop. Cancelled by the worker's ``on_shutdown`` hook."""
    logger.info("scheduler loop started (tick=%ss)", tick_seconds)
    try:
        while True:
            try:
                await _tick(cfg, session_factory, pool)
            except Exception:
                logger.exception("scheduler tick raised; continuing")
            await asyncio.sleep(tick_seconds)
    except asyncio.CancelledError:
        logger.info("scheduler loop cancelled")
        raise
