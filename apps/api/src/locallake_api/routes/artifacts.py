# SPDX-License-Identifier: Apache-2.0
"""Artifact routes — list, download, and parquet preview.

Artifacts live in the per-run dir resolved by ``run_dir_for(cfg, job_id)``.
All path inputs from the client are validated to stay inside that dir.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun
from locallake_core.runs import run_dir_for

from locallake_api.deps import get_config, get_session_factory
from locallake_api.schemas import (
    ArtifactEntryOut,
    ArtifactListOut,
    ArtifactPreviewOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["artifacts"])

# Preview limits — keep payloads small and bounded.
_PREVIEW_MAX_ROWS = 100
_PREVIEW_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MiB
_PREVIEWABLE_SUFFIXES = {".parquet"}


def _resolve_artifact_root(
    cfg: LakehouseConfig,
    factory: Any,
    job_id: str,
) -> Path:
    """Look up the JobRun + return its (validated) artifact root, or 404."""
    session = factory()
    try:
        run: JobRun | None = session.get(JobRun, job_id)
    finally:
        session.close()
    if run is None:
        raise HTTPException(404, f"job not found: {job_id}")
    return run_dir_for(cfg, job_id)


def _resolve_under(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``; reject anything that escapes."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise HTTPException(400, f"invalid artifact path: {rel!r}")
    full = (root / p).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(400, f"artifact path escapes run dir: {rel!r}") from exc
    return full


@router.get("/{job_id}/artifacts", response_model=ArtifactListOut)
async def list_artifacts(
    job_id: str,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> ArtifactListOut:
    root = _resolve_artifact_root(cfg, factory, job_id)
    if not root.is_dir():
        return ArtifactListOut(items=[], total=0)
    items: list[ArtifactEntryOut] = []
    for entry in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not entry.is_file():
            continue
        stat = entry.stat()
        items.append(
            ArtifactEntryOut(
                path=str(entry.relative_to(root).as_posix()),
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                previewable=entry.suffix.lower() in _PREVIEWABLE_SUFFIXES,
            )
        )
    return ArtifactListOut(items=items, total=len(items))


@router.get("/{job_id}/artifacts/{artifact_path:path}/preview", response_model=ArtifactPreviewOut)
async def preview_artifact(
    job_id: str,
    artifact_path: str,
    rows: int = Query(default=50, ge=1, le=_PREVIEW_MAX_ROWS),
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> ArtifactPreviewOut:
    root = _resolve_artifact_root(cfg, factory, job_id)
    full = _resolve_under(root, artifact_path)
    if not full.is_file():
        raise HTTPException(404, f"artifact not found: {artifact_path}")
    if full.suffix.lower() not in _PREVIEWABLE_SUFFIXES:
        raise HTTPException(415, f"no preview for suffix {full.suffix!r}")
    if full.stat().st_size > _PREVIEW_MAX_FILE_BYTES:
        raise HTTPException(413, "artifact too large to preview")

    # Read-only, in-memory DuckDB — no contention with the workspace db.
    conn = duckdb.connect(":memory:", read_only=False)
    try:
        rel = conn.read_parquet(str(full))
        sample = rel.limit(rows).fetchall()
        columns = [c[0] for c in rel.description]
        total_row = conn.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(full)]).fetchone()
        total = int(total_row[0]) if total_row else 0
    except duckdb.Error as exc:
        raise HTTPException(422, f"parquet read failed: {exc}") from exc
    finally:
        conn.close()

    serialized = [[_jsonable(v) for v in row] for row in sample]
    return ArtifactPreviewOut(
        columns=columns,
        rows=serialized,
        total_rows=total,
        truncated=total > len(serialized),
    )


@router.get("/{job_id}/artifacts/{artifact_path:path}")
async def download_artifact(
    job_id: str,
    artifact_path: str,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> FileResponse:
    root = _resolve_artifact_root(cfg, factory, job_id)
    full = _resolve_under(root, artifact_path)
    if not full.is_file():
        raise HTTPException(404, f"artifact not found: {artifact_path}")
    return FileResponse(
        path=str(full),
        filename=full.name,
        media_type="application/octet-stream",
    )


def _jsonable(v: Any) -> Any:
    """Coerce DuckDB row cells to JSON-safe scalars for the preview payload."""
    if v is None or isinstance(v, bool | int | float | str):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)
