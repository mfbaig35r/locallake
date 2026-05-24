# SPDX-License-Identifier: Apache-2.0
"""WebSocket routes for LocalLake — log streaming.

IMPORTANT: every route in this module MUST be defined at module scope.
Wrapping ``@router.websocket(...)`` (or ``@app.websocket(...)``) inside a
factory function makes FastAPI return HTTP 403 on the handshake. See the
note in ``PLAN.md`` §10 and the cross-project memory entry on FastAPI
websocket routes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun
from locallake_core.runs import LOG_FOOTER_SENTINEL, log_path_for

from locallake_api.deps import get_config, get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])

_TERMINAL_STATUSES = frozenset({"success", "failed", "cancelled", "timed_out"})
_READ_CHUNK = 8192
_POLL_INTERVAL_S = 0.4
# Cap on time we keep an idle WS open after the job reaches a terminal status
# but the log file is still empty (e.g. notebook crashed before init_log_file).
_TERMINAL_GRACE_S = 2.0


def _job_status(factory: Any, job_id: str) -> str | None:
    session = factory()
    try:
        run: JobRun | None = session.get(JobRun, job_id)
        return run.status if run else None
    finally:
        session.close()


@router.websocket("/jobs/{job_id}/logs")
async def stream_job_logs(
    websocket: WebSocket,
    job_id: str,
    cfg: LakehouseConfig = Depends(get_config),
    factory: Any = Depends(get_session_factory),
) -> None:
    """Tail the per-run log file and forward it line-by-line over a WS.

    Sends text frames (one per ``send_text`` call) containing zero or more
    lines. Closes the socket once the job is in a terminal status AND the
    sentinel footer has been forwarded (or after a short grace period if the
    log file never materialized).
    """
    await websocket.accept()
    status = _job_status(factory, job_id)
    if status is None:
        await websocket.send_text("[error] job not found\n")
        await websocket.close()
        return

    log_path = log_path_for(cfg, job_id)
    offset = 0
    terminal_seen_at: float | None = None
    sentinel_forwarded = False

    try:
        while True:
            if log_path.exists():
                try:
                    with open(log_path, "rb") as fh:
                        fh.seek(offset)
                        chunk = fh.read(_READ_CHUNK)
                except OSError as exc:
                    await websocket.send_text(f"[error] reading log: {exc}\n")
                    break

                if chunk:
                    offset += len(chunk)
                    text = chunk.decode("utf-8", errors="replace")
                    await websocket.send_text(text)
                    if LOG_FOOTER_SENTINEL in text:
                        sentinel_forwarded = True
                        # Drain anything written after the sentinel within
                        # the same poll, then close on the next loop pass.

            status = _job_status(factory, job_id) or status
            if status in _TERMINAL_STATUSES:
                if sentinel_forwarded:
                    break
                now = asyncio.get_event_loop().time()
                if terminal_seen_at is None:
                    terminal_seen_at = now
                elif now - terminal_seen_at > _TERMINAL_GRACE_S:
                    # Job ended but never wrote a footer — close anyway.
                    break

            await asyncio.sleep(_POLL_INTERVAL_S)
    except WebSocketDisconnect:
        return
    finally:
        # Already-closed sockets raise RuntimeError on a second close().
        with contextlib.suppress(RuntimeError):
            await websocket.close()
