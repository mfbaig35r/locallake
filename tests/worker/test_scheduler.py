# SPDX-License-Identifier: Apache-2.0
"""Worker scheduler — exercises _tick deterministically with frozen time."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def _seed_schedule(
    factory: Any,
    *,
    cron: str = "0 * * * *",
    enabled: bool = True,
    last_run_at: datetime | None = None,
    notebook_path: str = "hello.py",
    params_json: str = "{}",
) -> str:
    s = factory()
    try:
        sched = Schedule(
            notebook_path=notebook_path,
            cron_expression=cron,
            enabled=enabled,
            last_run_at=last_run_at,
            created_at=datetime.now(UTC),
            parameters_json=params_json,
        )
        s.add(sched)
        s.commit()
        s.refresh(sched)
        return sched.id
    finally:
        s.close()


async def test_tick_fires_due_schedule(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.scheduler import _tick

    sched_id = _seed_schedule(factory, cron="0 * * * *")
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()

    moment = datetime(2026, 5, 24, 10, 0, 30, tzinfo=UTC)
    fired = await _tick(cfg, factory, pool, now=moment)

    assert fired == [sched_id]
    pool.enqueue_job.assert_awaited_once()
    # And the row was updated.
    s = factory()
    try:
        row = s.get(Schedule, sched_id)
        assert row is not None
        assert row.last_run_at is not None
        assert row.last_run_id is not None
        # JobRun was created with the schedule-triggered marker.
        run = s.get(JobRun, row.last_run_id)
        assert run is not None
        assert run.triggered_by == "schedule"
    finally:
        s.close()


async def test_tick_skips_disabled(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.scheduler import _tick

    _seed_schedule(factory, cron="0 * * * *", enabled=False)
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    fired = await _tick(cfg, factory, pool, now=datetime(2026, 5, 24, 10, 0, 30, tzinfo=UTC))
    assert fired == []
    pool.enqueue_job.assert_not_called()


async def test_tick_does_not_double_fire(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.scheduler import _tick

    _seed_schedule(factory, cron="0 * * * *")
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    moment = datetime(2026, 5, 24, 10, 0, 30, tzinfo=UTC)
    await _tick(cfg, factory, pool, now=moment)
    # Same minute again — already fired.
    second = await _tick(cfg, factory, pool, now=moment + timedelta(seconds=5))
    assert second == []


async def test_tick_handles_invalid_cron(cfg: LakehouseConfig, factory: Any) -> None:
    from locallake_worker.scheduler import _tick

    # Bypass route validation by writing directly.
    s = factory()
    try:
        s.add(
            Schedule(
                notebook_path="hello.py",
                cron_expression="not a cron",
                enabled=True,
                created_at=datetime.now(UTC),
                parameters_json="{}",
            )
        )
        s.commit()
    finally:
        s.close()

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    fired = await _tick(cfg, factory, pool, now=datetime(2026, 5, 24, 10, 0, 30, tzinfo=UTC))
    assert fired == []
    pool.enqueue_job.assert_not_called()
