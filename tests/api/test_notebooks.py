# SPDX-License-Identifier: Apache-2.0
"""POST /notebooks/{path}/run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from locallake_core.config import LakehouseConfig


def test_run_notebook_returns_queued_job(
    client: TestClient,
    lake_config: LakehouseConfig,
    mock_pool: Any,
) -> None:
    (Path(lake_config.paths.notebooks) / "hello.py").write_text("# hi")
    r = client.post("/notebooks/hello.py/run", json={"parameters": {"k": "v"}})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["notebook_path"] == "hello.py"
    assert body["triggered_by"] == "api"
    assert body["id"]
    mock_pool.enqueue_job.assert_awaited_once_with("run_notebook", body["id"])


def test_run_notebook_404_for_missing_file(
    client: TestClient, lake_config: LakehouseConfig
) -> None:
    r = client.post("/notebooks/missing.py/run")
    assert r.status_code == 404


def test_run_notebook_rejects_traversal(client: TestClient) -> None:
    r = client.post("/notebooks/..%2Fescape.py/run")
    # FastAPI's path:path will normalize this; either way it should fail validation
    assert r.status_code in (400, 404)


def test_run_notebook_subdirectory(
    client: TestClient, lake_config: LakehouseConfig, mock_pool: Any
) -> None:
    sub = Path(lake_config.paths.notebooks) / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("# nested")
    r = client.post("/notebooks/sub/nested.py/run", json={})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["notebook_path"] == "sub/nested.py"
