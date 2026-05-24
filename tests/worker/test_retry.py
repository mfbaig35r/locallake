# SPDX-License-Identifier: Apache-2.0
"""Schedule retry — chain depth + max_retries gating."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from locallake_core.config import (
    DatabaseConfig,
    LakehouseConfig,
    PathsConfig,
    WorkspaceMeta,
)
from locallake_core.db import make_session_factory
from locallake_core.models import Base, JobRun, Schedule


@pytest.fixture
def cfg(tmp_path: Path) -> LakehouseConfig:
    root = tmp_path / "workspace"
    for sub in ("notebooks", "artifacts", "logs", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (root / "notebooks" / "hello.py").write_text("# nb\n")
    return LakehouseConfig(
        workspace=WorkspaceMeta(name="t", root_path=str(root)),
        database=DatabaseConfig(type="duckdb", path=str(tmp_path / "data" / "x.duckdb")),
        paths=PathsConfig(
            notebooks=str(root / "notebooks"),
            artifacts=str(root / "artifacts"),
            logs=str(root / "logs"),
            templates=str(root / "templates"),
        ),
    )


@pytest.fixture
def factory(tmp_path: Path) -> Any:
    f = make_session_factory(str(tmp_path / "meta.sqlite"))
    Base.metadata.create_all(f.kw["bind"])
    return f


def _make_schedule(factory: Any, *, max_retries: int) -> str:
    s = factory()
    try:
        sched = Schedule(
            notebook_path="hello.py",
            cron_expression="0 * * * *",
            enabled=True,
            created_at=datetime.now(UTC),
            parameters_json="{}",
            max_retries=max_retries,
        )
        s.add(sched)
        s.commit()
        s.refresh(sched)
        return sched.id
    finally:
        s.close()


def _make_failed_run(
    factory: Any,
    *,
    schedule_id: str | None,
    parent_run_id: str | None = None,
) -> str:
    s = factory()
    try:
        run = JobRun(
            notebook_path="hello.py",
            status="failed",
            created_at=datetime.now(UTC),
            triggered_by="schedule" if schedule_id else "api",
            parameters_json="{}",
            timeout_seconds=60,
            schedule_id=schedule_id,
            parent_run_id=parent_run_id,
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        return run.id
    finally:
        s.close()


async def test_retry_enqueues_child_within_budget(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.retry import maybe_retry

    sched_id = _make_schedule(factory, max_retries=2)
    failed = _make_failed_run(factory, schedule_id=sched_id)

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    child = await maybe_retry(cfg, factory, pool, failed)
    assert child is not None
    pool.enqueue_job.assert_awaited_once()
    # The defer kwarg means the second positional was the new job_id.
    call = pool.enqueue_job.await_args
    assert call.args[0] == "run_notebook"
    assert call.kwargs.get("_defer_by") == 60

    # The child row has parent_run_id pointing back.
    s = factory()
    try:
        cr = s.get(JobRun, child)
        assert cr is not None
        assert cr.parent_run_id == failed
        assert cr.schedule_id == sched_id
        assert cr.triggered_by == "retry"
    finally:
        s.close()


async def test_retry_stops_at_budget(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.retry import maybe_retry

    sched_id = _make_schedule(factory, max_retries=1)
    # Chain: original -> retry1 (failed). Already at the budget (1 original + 1 retry).
    original = _make_failed_run(factory, schedule_id=sched_id)
    retry1 = _make_failed_run(factory, schedule_id=sched_id, parent_run_id=original)

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    child = await maybe_retry(cfg, factory, pool, retry1)
    assert child is None
    pool.enqueue_job.assert_not_called()


async def test_retry_skips_non_schedule_run(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.retry import maybe_retry

    failed = _make_failed_run(factory, schedule_id=None)
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    assert await maybe_retry(cfg, factory, pool, failed) is None
    pool.enqueue_job.assert_not_called()


async def test_retry_skips_when_max_retries_zero(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.retry import maybe_retry

    sched_id = _make_schedule(factory, max_retries=0)
    failed = _make_failed_run(factory, schedule_id=sched_id)
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    assert await maybe_retry(cfg, factory, pool, failed) is None
    pool.enqueue_job.assert_not_called()


async def test_retry_skips_for_success(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.retry import maybe_retry

    sched_id = _make_schedule(factory, max_retries=2)
    # Insert a SUCCESS run, not failed — maybe_retry only fires on failed.
    s = factory()
    try:
        run = JobRun(
            notebook_path="hello.py",
            status="success",
            created_at=datetime.now(UTC),
            triggered_by="schedule",
            parameters_json="{}",
            timeout_seconds=60,
            schedule_id=sched_id,
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    finally:
        s.close()

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    assert await maybe_retry(cfg, factory, pool, run_id) is None
    pool.enqueue_job.assert_not_called()
