# SPDX-License-Identifier: Apache-2.0
"""Schedule-driven retry policy — Phase 7.

If a JobRun ends in 'failed' AND it was triggered by a schedule AND the
schedule has ``max_retries > 0``, enqueue a child JobRun (linked via
``parent_run_id``) until the chain depth hits the cap. The retry uses the
same notebook, parameters, and schedule_id; the worker arms a 60-second
arq defer so retries don't hammer immediately.

Manual-run retries are intentionally NOT covered — they're an orthogonal
design call (where does max_retries live for an ad-hoc run?). Retry only
fires for schedule-triggered runs in v1.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun, Schedule
from locallake_core.runs import submit_job
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Fixed delay between attempts. Exponential backoff is overkill for v1 since
# we cap retries low (typical max_retries = 1..3). Revisit if users ask.
RETRY_DEFER_SECONDS = 60


def _chain_depth(session: Session, leaf_id: str) -> int:
    """Walk ``parent_run_id`` from ``leaf_id`` and return chain length (1+)."""
    depth = 0
    cursor: str | None = leaf_id
    while cursor is not None and depth < 100:  # cycle guard
        depth += 1
        row = session.get(JobRun, cursor)
        if row is None:
            break
        cursor = row.parent_run_id
    return depth


async def maybe_retry(
    cfg: LakehouseConfig,
    session_factory: sessionmaker[Session],
    pool: Any,
    failed_job_id: str,
) -> str | None:
    """If retries remain, enqueue a child JobRun. Returns the child id or None."""
    session = session_factory()
    try:
        run = session.get(JobRun, failed_job_id)
        if run is None or run.status != "failed":
            return None
        schedule_id = run.schedule_id
        if not schedule_id:
            return None
        schedule = session.get(Schedule, schedule_id)
        if schedule is None or schedule.max_retries <= 0:
            return None
        # Total attempts allowed = 1 (original) + max_retries.
        attempts_so_far = _chain_depth(session, failed_job_id)
        if attempts_so_far > schedule.max_retries:
            logger.info(
                "schedule %s: retry budget exhausted (%d/%d attempts)",
                schedule_id,
                attempts_so_far,
                schedule.max_retries + 1,
            )
            return None
        try:
            params = json.loads(run.parameters_json or "{}")
        except json.JSONDecodeError:
            params = {}
        notebook_path = run.notebook_path
    finally:
        session.close()

    child = await submit_job(
        cfg,
        session_factory,
        pool,
        notebook_path=notebook_path,
        parameters=params,
        triggered_by="retry",
        parent_run_id=failed_job_id,
        schedule_id=schedule_id,
        defer_seconds=RETRY_DEFER_SECONDS,
    )
    logger.info(
        "schedule %s: enqueued retry %s of %s (attempt %d/%d)",
        schedule_id,
        child.id,
        failed_job_id,
        attempts_so_far + 1,
        schedule.max_retries + 1,
    )
    return child.id
