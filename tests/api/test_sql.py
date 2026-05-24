# SPDX-License-Identifier: Apache-2.0
"""/sql/query, /sql/saved, /sql/history endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
from locallake_core.config import LakehouseConfig
from locallake_core.models import QueryHistory


def _seed_workspace_db(cfg: LakehouseConfig) -> None:
    db = cfg.database.path
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS items(id INTEGER, name TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'a'), (2, 'b')")
    conn.close()


def test_query_runs_and_records_history(
    client: Any, lake_config: LakehouseConfig, session_factory: Any
) -> None:
    _seed_workspace_db(lake_config)
    res = client.post("/sql/query", json={"sql": "SELECT * FROM items ORDER BY id"})
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["id", "name"]
    assert body["rows"] == [[1, "a"], [2, "b"]]
    assert body["truncated"] is False

    # History row written
    session = session_factory()
    try:
        history = session.query(QueryHistory).all()
    finally:
        session.close()
    assert len(history) == 1
    assert history[0].row_count == 2
    assert history[0].error_message is None


def test_query_400_on_disallowed_statement(client: Any) -> None:
    res = client.post("/sql/query", json={"sql": "DROP TABLE items"})
    assert res.status_code == 400
    assert "allowed" in res.json()["detail"]


def test_query_records_failure_in_history(
    client: Any, lake_config: LakehouseConfig, session_factory: Any
) -> None:
    _seed_workspace_db(lake_config)
    res = client.post("/sql/query", json={"sql": "SELECT * FROM nope"})
    assert res.status_code == 422

    session = session_factory()
    try:
        history = session.query(QueryHistory).all()
    finally:
        session.close()
    assert len(history) == 1
    assert history[0].error_message is not None


def test_saved_queries_crud(client: Any) -> None:
    res = client.post("/sql/saved", json={"name": "all items", "sql": "SELECT * FROM items"})
    assert res.status_code == 201
    saved = res.json()
    assert saved["name"] == "all items"
    saved_id = saved["id"]

    listing = client.get("/sql/saved").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == saved_id

    dup = client.post("/sql/saved", json={"name": "all items", "sql": "SELECT 1"})
    assert dup.status_code == 409

    delete = client.delete(f"/sql/saved/{saved_id}")
    assert delete.status_code == 204
    assert client.get("/sql/saved").json()["total"] == 0


def test_delete_unknown_saved_returns_404(client: Any) -> None:
    res = client.delete("/sql/saved/does-not-exist")
    assert res.status_code == 404


def test_history_returns_most_recent_first(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_workspace_db(lake_config)
    client.post("/sql/query", json={"sql": "SELECT 1 AS first"})
    client.post("/sql/query", json={"sql": "SELECT 2 AS second"})
    res = client.get("/sql/history?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    # Newest first
    assert "second" in body["items"][0]["sql"]
    assert "first" in body["items"][1]["sql"]
