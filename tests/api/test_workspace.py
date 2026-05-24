# SPDX-License-Identifier: Apache-2.0
"""GET /workspace — exposes the workspace config to the UI."""

from __future__ import annotations

from typing import Any

from locallake_core.config import LakehouseConfig


def test_workspace_endpoint_returns_config(client: Any, lake_config: LakehouseConfig) -> None:
    res = client.get("/workspace")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == lake_config.workspace.name
    assert body["root_path"] == lake_config.workspace.root_path
    assert body["database_path"] == lake_config.database.path
    assert body["paths"]["notebooks"] == lake_config.paths.notebooks
    assert "worker_concurrency" in body
    assert isinstance(body["worker_concurrency"], int)
