# SPDX-License-Identifier: Apache-2.0
"""WebSocket log streaming — exercises the module-level route end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun
from locallake_core.runs import LOG_FOOTER_SENTINEL, log_path_for


def _seed(factory: Any, *, status: str) -> str:
    s = factory()
    try:
        r = JobRun(
            notebook_path="x.py",
            status=status,
            created_at=datetime.now(UTC),
            triggered_by="test",
            parameters_json="{}",
            timeout_seconds=60,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def test_ws_streams_log_then_closes_on_terminal_status(
    client: Any, lake_config: LakehouseConfig, session_factory: Any
) -> None:
    job_id = _seed(session_factory, status="success")
    log_path = log_path_for(lake_config, job_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"first line\nsecond line\n--- \n{LOG_FOOTER_SENTINEL} status=success\n",
        encoding="utf-8",
    )

    with client.websocket_connect(f"/jobs/{job_id}/logs") as ws:
        chunks: list[str] = []
        while True:
            try:
                chunks.append(ws.receive_text())
            except Exception:
                break
            if LOG_FOOTER_SENTINEL in "".join(chunks):
                break
    body = "".join(chunks)
    assert "first line" in body
    assert "second line" in body
    assert LOG_FOOTER_SENTINEL in body


def test_ws_unknown_job_emits_error_then_closes(client: Any) -> None:
    with client.websocket_connect("/jobs/missing/logs") as ws:
        msg = ws.receive_text()
        assert "job not found" in msg
