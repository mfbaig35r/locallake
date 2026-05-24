# SPDX-License-Identifier: Apache-2.0
"""execute_job — mocked marimo-sandbox call, verifies env wiring + row updates."""

from __future__ import annotations

import os
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from locallake_core.config import (
    DatabaseConfig,
    LakehouseConfig,
    PathsConfig,
    WorkspaceMeta,
)
from locallake_core.db import make_session_factory
from locallake_core.models import Base, JobRun


@pytest.fixture
def cfg(tmp_path: Path) -> LakehouseConfig:
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


@pytest.fixture
def factory(tmp_path: Path) -> Any:
    f = make_session_factory(str(tmp_path / "meta.sqlite"))
    Base.metadata.create_all(f.kw["bind"])
    return f


@pytest.fixture
def fake_marimo_sandbox(monkeypatch):
    """Inject a synthetic marimo_sandbox.server with a configurable _impl_run_python.

    Yields the mock so each test can set its return value.
    """
    mock_impl = MagicMock()
    fake_server = types.ModuleType("marimo_sandbox.server")
    fake_server._impl_run_python = mock_impl  # type: ignore[attr-defined]
    fake_pkg = types.ModuleType("marimo_sandbox")

    monkeypatch.setitem(sys.modules, "marimo_sandbox", fake_pkg)
    monkeypatch.setitem(sys.modules, "marimo_sandbox.server", fake_server)
    return mock_impl


def _seed_run(factory: Any, *, notebook_path: str, status: str = "queued") -> str:
    s = factory()
    try:
        r = JobRun(
            notebook_path=notebook_path,
            status=status,
            created_at=datetime.now(UTC),
            triggered_by="test",
            parameters_json='{"alpha": 1}',
            timeout_seconds=60,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def test_execute_job_success_path(
    cfg: LakehouseConfig, factory: Any, fake_marimo_sandbox: MagicMock
) -> None:
    from locallake_core.runs import LOG_FOOTER_SENTINEL, log_path_for
    from locallake_worker.runner import execute_job

    (Path(cfg.paths.notebooks) / "nb.py").write_text("# nb body\nprint(1)\n")
    job_id = _seed_run(factory, notebook_path="nb.py")

    fake_marimo_sandbox.return_value = {
        "status": "success",
        "run_id": "marimo-abc",
        "duration_ms": 1234,
        "stdout": "hello",
        "stderr": "",
    }

    out = execute_job(cfg, factory, job_id)
    assert out["status"] == "success"
    assert out["mcp_run_id"] == "marimo-abc"

    log_text = log_path_for(cfg, job_id).read_text(encoding="utf-8")
    assert "=== locallake run ===" in log_text
    assert "[stdout]" in log_text
    assert "hello" in log_text
    assert f"{LOG_FOOTER_SENTINEL} status=success" in log_text

    # marimo_sandbox call inspection — verifies context was injected + env set
    call = fake_marimo_sandbox.call_args
    assert "__lake__" in call.kwargs["code"]
    assert call.kwargs["code"].rstrip().endswith("print(1)")
    assert "marimo" in call.kwargs["packages"]
    assert call.kwargs["sandbox"] is False
    assert call.kwargs["async_mode"] is False
    assert call.kwargs["timeout_seconds"] == 60

    s = factory()
    try:
        r = s.get(JobRun, job_id)
        assert r is not None
        assert r.status == "success"
        assert r.mcp_run_id == "marimo-abc"
        assert r.started_at is not None
        assert r.finished_at is not None
        assert r.artifact_path is not None
        assert r.log_path is not None
        assert r.error_message is None
    finally:
        s.close()


def test_execute_job_failure_records_error(
    cfg: LakehouseConfig, factory: Any, fake_marimo_sandbox: MagicMock
) -> None:
    from locallake_worker.runner import execute_job

    (Path(cfg.paths.notebooks) / "nb.py").write_text("# nb\n")
    job_id = _seed_run(factory, notebook_path="nb.py")

    fake_marimo_sandbox.return_value = {
        "status": "error",
        "error": "ModuleNotFoundError: yikes",
        "run_id": "marimo-err",
    }

    out = execute_job(cfg, factory, job_id)
    assert out["status"] == "failed"

    s = factory()
    try:
        r = s.get(JobRun, job_id)
        assert r is not None
        assert r.status == "failed"
        assert r.error_message == "ModuleNotFoundError: yikes"
    finally:
        s.close()


def test_execute_job_skips_pre_cancelled(
    cfg: LakehouseConfig, factory: Any, fake_marimo_sandbox: MagicMock
) -> None:
    from locallake_worker.runner import execute_job

    (Path(cfg.paths.notebooks) / "nb.py").write_text("# nb\n")
    job_id = _seed_run(factory, notebook_path="nb.py", status="cancelled")

    out = execute_job(cfg, factory, job_id)
    assert out["status"] == "cancelled"
    assert out.get("skipped") is True
    fake_marimo_sandbox.assert_not_called()


def test_execute_job_404_for_missing_notebook(
    cfg: LakehouseConfig, factory: Any, fake_marimo_sandbox: MagicMock
) -> None:
    from locallake_core.runs import log_path_for
    from locallake_worker.runner import execute_job

    job_id = _seed_run(factory, notebook_path="ghost.py")

    with pytest.raises(FileNotFoundError):
        execute_job(cfg, factory, job_id)

    s = factory()
    try:
        r = s.get(JobRun, job_id)
        assert r is not None
        assert r.status == "failed"
        assert r.error_message is not None
        assert "not found" in r.error_message
    finally:
        s.close()

    # Even the missing-notebook path writes a log with a footer so the WS
    # tailer can close cleanly.
    log_text = log_path_for(cfg, job_id).read_text(encoding="utf-8")
    assert "notebook file not found" in log_text
    assert "status=failed" in log_text


def test_execute_job_restores_env_after_call(
    cfg: LakehouseConfig, factory: Any, fake_marimo_sandbox: MagicMock
) -> None:
    from locallake_worker.runner import execute_job

    (Path(cfg.paths.notebooks) / "nb.py").write_text("# nb\n")
    job_id = _seed_run(factory, notebook_path="nb.py")

    fake_marimo_sandbox.return_value = {"status": "success", "run_id": "x"}
    pre = dict(os.environ)
    execute_job(cfg, factory, job_id)
    post = dict(os.environ)
    # No LOCALLAKE_RUN_* should leak out of execute_job
    assert {k for k in post if k.startswith("LOCALLAKE_RUN_")} == {
        k for k in pre if k.startswith("LOCALLAKE_RUN_")
    }
