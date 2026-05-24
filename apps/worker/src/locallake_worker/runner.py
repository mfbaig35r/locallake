# SPDX-License-Identifier: Apache-2.0
"""Worker-side job execution.

Reads the notebook file, prepends the ``__lake__`` context template, sets up
the per-run env (db path, workspace path, artifacts dir, log path, params),
calls ``marimo_sandbox._impl_run_python``, captures the result, and updates
the ``JobRun`` row.

marimo-sandbox is imported lazily so locallake_core can be tested without it.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from locallake_core.config import LakehouseConfig
from locallake_core.context import inject_context, required_packages
from locallake_core.models import JobRun
from locallake_core.runs import (
    append_log_block,
    append_log_footer,
    init_log_file,
    log_path_for,
    mark_finished,
    mark_started,
    run_dir_for,
)
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


@contextmanager
def _patched_env(extra: dict[str, str]) -> Iterator[None]:
    """Set env vars for the marimo subprocess; restore on exit."""
    previous: dict[str, str | None] = {k: os.environ.get(k) for k in extra}
    os.environ.update(extra)
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _map_marimo_status(status: str) -> str:
    """Map marimo-sandbox status → LocalLake JobRun.status."""
    s = (status or "").lower()
    if s == "success":
        return "success"
    if s in {"error", "failed"}:
        return "failed"
    if s == "cancelled":
        return "cancelled"
    if s == "timeout":
        return "timed_out"
    return "failed"


def execute_job(
    cfg: LakehouseConfig,
    session_factory: sessionmaker[Session],
    job_id: str,
) -> dict[str, Any]:
    """Execute one queued JobRun. Updates the row to its terminal state."""
    session = session_factory()
    try:
        run: JobRun | None = session.get(JobRun, job_id)
    finally:
        session.close()
    if run is None:
        raise ValueError(f"JobRun {job_id} not found")

    # Honor pre-execution cancellation (API may have flipped status while task queued).
    if run.status == "cancelled":
        logger.info("job %s already cancelled before execution; skipping", job_id)
        return {"status": "cancelled", "skipped": True}

    notebooks_root = Path(cfg.paths.notebooks).resolve()
    nb_full = (notebooks_root / run.notebook_path).resolve()
    artifacts_dir = run_dir_for(cfg, job_id)
    log_path = log_path_for(cfg, job_id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    init_log_file(log_path, job_id, run.notebook_path)

    if not nb_full.is_file():
        append_log_block(log_path, "error", f"notebook file not found: {run.notebook_path}")
        append_log_footer(log_path, "failed")
        mark_finished(
            session_factory,
            job_id,
            status="failed",
            mcp_run_id=None,
            error_message=f"notebook file not found: {run.notebook_path}",
            artifact_path=str(artifacts_dir),
            log_path=str(log_path),
        )
        raise FileNotFoundError(nb_full)

    user_code = nb_full.read_text(encoding="utf-8")
    code = inject_context(user_code)

    env = {
        "LOCALLAKE_DB_PATH": cfg.database.path,
        "LOCALLAKE_WORKSPACE_PATH": cfg.workspace.root_path,
        "LOCALLAKE_RUN_ARTIFACTS_DIR": str(artifacts_dir),
        "LOCALLAKE_RUN_LOG_PATH": str(log_path),
        "LOCALLAKE_RUN_PARAMS": run.parameters_json or "{}",
    }

    mark_started(session_factory, job_id)
    logger.info("executing job %s (notebook=%s)", job_id, run.notebook_path)

    # Lazy import — keeps marimo-sandbox out of locallake_core's dep surface.
    from marimo_sandbox.server import _impl_run_python

    with _patched_env(env):
        result = _impl_run_python(
            code=code,
            description=f"locallake:{run.notebook_path}",
            packages=required_packages(),
            timeout_seconds=run.timeout_seconds,
            sandbox=False,
            async_mode=False,
        )

    raw_status = result.get("status", "")
    mapped = _map_marimo_status(raw_status)
    err = result.get("error") or result.get("stderr") if mapped != "success" else None

    # Tee captured stdout/stderr from marimo-sandbox into the run log. marimo
    # buffers both via subprocess.PIPE and only releases them when the run
    # completes, so users see __lake__.log() output live and print() lines as
    # one block at the end.
    stdout = result.get("stdout") or ""
    stderr = result.get("stderr") or ""
    if isinstance(stdout, str) and stdout.strip():
        append_log_block(log_path, "stdout", stdout)
    if isinstance(stderr, str) and stderr.strip():
        append_log_block(log_path, "stderr", stderr)
    append_log_footer(log_path, mapped)

    mark_finished(
        session_factory,
        job_id,
        status=mapped,
        mcp_run_id=result.get("run_id"),
        error_message=err if isinstance(err, str) else (json.dumps(err) if err else None),
        artifact_path=str(artifacts_dir),
        log_path=str(log_path),
    )

    logger.info(
        "job %s finished status=%s mcp_run_id=%s duration_ms=%s",
        job_id,
        mapped,
        result.get("run_id"),
        result.get("duration_ms"),
    )
    return {
        "job_id": job_id,
        "status": mapped,
        "mcp_run_id": result.get("run_id"),
        "duration_ms": result.get("duration_ms"),
    }
