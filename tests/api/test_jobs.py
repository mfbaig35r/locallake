# SPDX-License-Identifier: Apache-2.0
"""GET /jobs, GET /jobs/{id}, POST /jobs/{id}/cancel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from locallake_core.models import JobRun


def _insert_run(
    factory: Any,
    *,
    status: str = "queued",
    notebook_path: str = "x.py",
    triggered_by: str = "test",
) -> str:
    s = factory()
    try:
        r = JobRun(
            notebook_path=notebook_path,
            status=status,
            created_at=datetime.now(UTC),
            triggered_by=triggered_by,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def test_list_jobs_empty(client: TestClient) -> None:
    r = client.get("/jobs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_jobs_filters_by_status(client: TestClient, session_factory: Any) -> None:
    _insert_run(session_factory, status="queued")
    _insert_run(session_factory, status="success")
    _insert_run(session_factory, status="queued")

    r = client.get("/jobs", params={"status": "queued"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["status"] == "queued"


def test_list_jobs_pagination(client: TestClient, session_factory: Any) -> None:
    for _ in range(5):
        _insert_run(session_factory)
    r = client.get("/jobs", params={"limit": 2, "offset": 1})
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1


def test_get_job_found(client: TestClient, session_factory: Any) -> None:
    job_id = _insert_run(session_factory)
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["id"] == job_id


def test_get_job_404(client: TestClient) -> None:
    r = client.get("/jobs/no-such-id")
    assert r.status_code == 404


def test_cancel_queued_job(client: TestClient, session_factory: Any) -> None:
    job_id = _insert_run(session_factory, status="queued")
    r = client.post(f"/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Verify persistence
    follow = client.get(f"/jobs/{job_id}")
    assert follow.json()["status"] == "cancelled"


def test_cancel_already_terminal_job(client: TestClient, session_factory: Any) -> None:
    job_id = _insert_run(session_factory, status="success")
    r = client.post(f"/jobs/{job_id}/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert "already" in body["message"]


def test_cancel_running_job_409(client: TestClient, session_factory: Any) -> None:
    job_id = _insert_run(session_factory, status="running")
    r = client.post(f"/jobs/{job_id}/cancel")
    assert r.status_code == 409


def test_cancel_missing_job_404(client: TestClient) -> None:
    r = client.post("/jobs/no-such-id/cancel")
    assert r.status_code == 404
