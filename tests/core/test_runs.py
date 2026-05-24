# SPDX-License-Identifier: Apache-2.0
"""submit_job flow + lifecycle helpers + path validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from locallake_core.config import (
    DatabaseConfig,
    LakehouseConfig,
    PathsConfig,
    WorkspaceMeta,
)
from locallake_core.db import make_session_factory
from locallake_core.models import Base, JobRun
from locallake_core.runs import (
    NotebookNotFoundError,
    NotebookPathError,
    mark_finished,
    mark_started,
    resolve_notebook_path,
    submit_job,
)


def _make_cfg(tmp_path: Path) -> LakehouseConfig:
    root = tmp_path / "workspace"
    for sub in ("notebooks", "artifacts", "logs", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
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


def _make_factory(tmp_path: Path):
    factory = make_session_factory(str(tmp_path / "meta.sqlite"))
    Base.metadata.create_all(factory.kw["bind"])
    return factory


def test_resolve_path_happy(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    (Path(cfg.paths.notebooks) / "ok.py").write_text("# ok")
    out = resolve_notebook_path(cfg, "ok.py")
    assert out.is_file()
    assert out.name == "ok.py"


def test_resolve_path_rejects_absolute(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    with pytest.raises(NotebookPathError):
        resolve_notebook_path(cfg, "/etc/passwd")


def test_resolve_path_rejects_traversal(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    with pytest.raises(NotebookPathError):
        resolve_notebook_path(cfg, "../escape.py")


def test_resolve_path_404(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    with pytest.raises(NotebookNotFoundError):
        resolve_notebook_path(cfg, "missing.py")


async def test_submit_job_creates_row_and_enqueues(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    (Path(cfg.paths.notebooks) / "hello.py").write_text("# nb")
    factory = _make_factory(tmp_path)
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()

    run = await submit_job(
        cfg,
        factory,
        pool,
        notebook_path="hello.py",
        parameters={"k": "v"},
        triggered_by="test",
        timeout_seconds=120,
    )

    assert run.id
    assert run.status == "queued"
    assert run.notebook_path == "hello.py"
    assert json.loads(run.parameters_json) == {"k": "v"}
    assert run.timeout_seconds == 120
    assert run.triggered_by == "test"

    pool.enqueue_job.assert_awaited_once_with("run_notebook", run.id)

    # Persisted
    session = factory()
    try:
        loaded = session.get(JobRun, run.id)
    finally:
        session.close()
    assert loaded is not None
    assert loaded.status == "queued"


def test_mark_started_then_finished(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    factory = _make_factory(tmp_path)

    session = factory()
    try:
        r = JobRun(notebook_path="x.py", status="queued", triggered_by="t")
        session.add(r)
        session.commit()
        session.refresh(r)
        run_id = r.id
    finally:
        session.close()

    mark_started(factory, run_id)
    session = factory()
    try:
        r = session.get(JobRun, run_id)
        assert r is not None
        assert r.status == "running"
        assert r.started_at is not None
    finally:
        session.close()

    mark_finished(
        factory,
        run_id,
        status="success",
        mcp_run_id="m-123",
        error_message=None,
        artifact_path=str(tmp_path / "art"),
        log_path=str(tmp_path / "log.log"),
    )
    session = factory()
    try:
        r = session.get(JobRun, run_id)
        assert r is not None
        assert r.status == "success"
        assert r.finished_at is not None
        assert r.duration_seconds is not None
        assert r.duration_seconds >= 0
        assert r.mcp_run_id == "m-123"
    finally:
        session.close()
    assert cfg.workspace.name == "t"  # touch cfg to keep _make_cfg fixture honest
