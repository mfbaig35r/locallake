# SPDX-License-Identifier: Apache-2.0
"""Run submission + shared helpers used by both API (submit) and worker (execute).

The API calls ``submit_job`` to create a ``JobRun`` row and enqueue an arq task.
The worker's ``execute_job`` (in ``locallake_worker.runner``) picks up the task,
calls marimo-sandbox, and updates the row.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from locallake_core.config import LakehouseConfig
from locallake_core.git_info import get_git_info
from locallake_core.models import JobRun

logger = logging.getLogger(__name__)


# Footer sentinel — the WebSocket log tailer uses this as a signal to close
# the stream after the last bytes have been forwarded. Match exactly when
# scanning; do not localize.
LOG_FOOTER_SENTINEL = "=== run complete ==="


class ArqPool(Protocol):
    """Subset of arq.ArqRedis we use — only ``enqueue_job``."""

    async def enqueue_job(
        self, function: str, *args: Any, **kwargs: Any
    ) -> Any:  # pragma: no cover - protocol
        ...


class NotebookNotFoundError(Exception):
    """Notebook path doesn't exist under the workspace notebooks dir."""


class NotebookPathError(ValueError):
    """Notebook path is invalid (absolute, traversal, escapes workspace)."""


def resolve_notebook_path(cfg: LakehouseConfig, notebook_path: str) -> Path:
    """Validate + resolve a workspace-relative notebook path.

    Rejects absolute paths, parent traversal (``..``), and any resolved path
    that lands outside ``cfg.paths.notebooks``.
    """
    p = Path(notebook_path)
    if p.is_absolute() or ".." in p.parts:
        raise NotebookPathError(
            f"notebook path must be relative without '..' (got {notebook_path!r})"
        )

    notebooks_root = Path(cfg.paths.notebooks).resolve()
    full = (notebooks_root / p).resolve()
    try:
        full.relative_to(notebooks_root)
    except ValueError as exc:
        raise NotebookPathError(
            f"notebook path escapes notebooks directory: {notebook_path!r}"
        ) from exc

    if not full.is_file():
        raise NotebookNotFoundError(f"notebook not found: {notebook_path}")
    return full


def _utc_now() -> datetime:
    return datetime.now(UTC)


def run_dir_for(cfg: LakehouseConfig, job_id: str) -> Path:
    """Per-run artifact directory under ``cfg.paths.artifacts``."""
    return Path(cfg.paths.artifacts) / "runs" / job_id


def log_path_for(cfg: LakehouseConfig, job_id: str) -> Path:
    """Per-run log file under ``cfg.paths.logs``."""
    return Path(cfg.paths.logs) / f"{job_id}.log"


def init_log_file(path: Path, job_id: str, notebook_path: str) -> None:
    """Create the log file with a header before execution starts.

    Idempotent: if the file already exists it is left alone so a re-entrant
    runner doesn't truncate live output.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== locallake run ===\njob_id: {job_id}\nnotebook: {notebook_path}\nstarted: {ts}\n---\n"
    )
    path.write_text(header, encoding="utf-8")


def append_log_block(path: Path, label: str, body: str) -> None:
    """Append a labeled block (e.g. ``[stdout]``) to a run log file."""
    if not body:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    text = body if body.endswith("\n") else body + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"[{label}]\n{text}")


def append_log_footer(path: Path, status: str) -> None:
    """Append the terminal footer that the WebSocket tailer keys on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"---\n{LOG_FOOTER_SENTINEL} status={status} at={ts}\n")


async def submit_job(
    cfg: LakehouseConfig,
    session_factory: sessionmaker[Session],
    pool: ArqPool,
    *,
    notebook_path: str,
    parameters: dict[str, Any] | None = None,
    triggered_by: str = "api",
    timeout_seconds: int = 300,
    parent_run_id: str | None = None,
    schedule_id: str | None = None,
    defer_seconds: int = 0,
) -> JobRun:
    """Validate notebook, capture git state, insert JobRun, enqueue arq task.

    ``parent_run_id`` + ``schedule_id`` are set by the schedule-driven retry
    path so the parent chain is walkable. ``defer_seconds`` delays the arq
    enqueue (used to space out retries).
    """
    full = resolve_notebook_path(cfg, notebook_path)

    git_sha, git_dirty = get_git_info(cfg.workspace.root_path)

    run = JobRun(
        notebook_path=str(full.relative_to(Path(cfg.paths.notebooks).resolve())),
        status="queued",
        created_at=_utc_now(),
        triggered_by=triggered_by,
        git_commit_sha=git_sha,
        git_dirty=git_dirty,
        parameters_json=json.dumps(parameters or {}),
        timeout_seconds=timeout_seconds,
        parent_run_id=parent_run_id,
        schedule_id=schedule_id,
    )

    session = session_factory()
    try:
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
    finally:
        session.close()

    if defer_seconds > 0:
        # arq accepts `_defer_by` (timedelta or seconds) for delayed enqueue.
        await pool.enqueue_job("run_notebook", run_id, _defer_by=defer_seconds)
    else:
        await pool.enqueue_job("run_notebook", run_id)
    logger.info(
        "submitted job %s for notebook %s (parent=%s, schedule=%s, defer=%ss)",
        run_id,
        notebook_path,
        parent_run_id,
        schedule_id,
        defer_seconds,
    )
    return run


def mark_started(session_factory: sessionmaker[Session], job_id: str) -> None:
    """Transition a JobRun from queued → running."""
    session = session_factory()
    try:
        run = session.get(JobRun, job_id)
        if run is None:
            raise ValueError(f"JobRun {job_id} not found")
        run.status = "running"
        run.started_at = _utc_now()
        session.commit()
    finally:
        session.close()


def mark_finished(
    session_factory: sessionmaker[Session],
    job_id: str,
    *,
    status: str,
    mcp_run_id: str | None,
    error_message: str | None,
    artifact_path: str | None,
    log_path: str | None,
) -> None:
    """Transition a JobRun to a terminal state."""
    session = session_factory()
    try:
        run = session.get(JobRun, job_id)
        if run is None:
            raise ValueError(f"JobRun {job_id} not found")
        finished = _utc_now()
        run.status = status
        run.finished_at = finished
        if run.started_at is not None:
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            run.duration_seconds = (finished - started).total_seconds()
        run.mcp_run_id = mcp_run_id
        run.error_message = error_message
        run.artifact_path = artifact_path
        run.log_path = log_path
        session.commit()
    finally:
        session.close()
