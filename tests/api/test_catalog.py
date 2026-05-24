# SPDX-License-Identifier: Apache-2.0
"""/catalog/tables routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
from locallake_core.config import LakehouseConfig


def _seed(cfg: LakehouseConfig) -> None:
    db = cfg.database.path
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(db)
    conn.execute("CREATE SCHEMA shop")
    conn.execute("CREATE TABLE shop.orders(id INTEGER, total DOUBLE)")
    conn.execute("INSERT INTO shop.orders VALUES (1, 9.99), (2, 19.5)")
    conn.execute("CREATE VIEW shop.big AS SELECT * FROM shop.orders WHERE total > 10")
    conn.close()


def test_list_tables(client: Any, lake_config: LakehouseConfig) -> None:
    _seed(lake_config)
    res = client.get("/catalog/tables")
    assert res.status_code == 200
    body = res.json()
    pairs = {(it["schema"], it["name"], it["kind"]) for it in body["items"]}
    assert ("shop", "orders", "table") in pairs
    assert ("shop", "big", "view") in pairs


def test_table_detail_includes_columns_and_sample(
    client: Any, lake_config: LakehouseConfig
) -> None:
    _seed(lake_config)
    res = client.get("/catalog/tables/shop/orders")
    assert res.status_code == 200
    body = res.json()
    assert body["row_count"] == 2
    col_names = {c["name"] for c in body["columns"]}
    assert col_names == {"id", "total"}
    assert body["sample_columns"] == ["id", "total"]
    assert len(body["sample_rows"]) == 2


def test_table_detail_404_for_missing(client: Any, lake_config: LakehouseConfig) -> None:
    _seed(lake_config)
    res = client.get("/catalog/tables/shop/ghost")
    assert res.status_code == 404


def test_table_detail_skips_sample_when_zero(client: Any, lake_config: LakehouseConfig) -> None:
    _seed(lake_config)
    res = client.get("/catalog/tables/shop/orders?sample_rows=0")
    body = res.json()
    assert body["sample_columns"] == []
    assert body["sample_rows"] == []
