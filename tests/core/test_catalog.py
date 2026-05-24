# SPDX-License-Identifier: Apache-2.0
"""Catalog introspection — list, describe, sample."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from locallake_core.catalog import describe_table, list_tables, sample_table


def _seed(tmp_path: Path) -> str:
    db = tmp_path / "cat.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("CREATE SCHEMA shop")
    conn.execute("CREATE TABLE shop.orders(id INTEGER, total DOUBLE, paid BOOLEAN)")
    conn.execute("INSERT INTO shop.orders VALUES (1, 9.99, true), (2, 19.5, false)")
    conn.execute("CREATE VIEW shop.paid_orders AS SELECT * FROM shop.orders WHERE paid")
    conn.close()
    return str(db)


def test_list_tables_returns_tables_and_views(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    entries = list_tables(db)
    pairs = {(e.schema, e.name, e.kind) for e in entries}
    assert ("shop", "orders", "table") in pairs
    assert ("shop", "paid_orders", "view") in pairs


def test_describe_table_returns_columns_and_row_count(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    detail = describe_table(db, "shop", "orders")
    assert detail is not None
    assert detail.kind == "table"
    assert detail.row_count == 2
    cols = {c.name: c for c in detail.columns}
    assert set(cols) == {"id", "total", "paid"}
    assert cols["total"].type.upper().startswith("DOUBLE")


def test_describe_missing_table_returns_none(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    assert describe_table(db, "shop", "no_such") is None


def test_sample_table_returns_rows(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    cols, rows = sample_table(db, "shop", "orders", limit=10)
    assert cols == ["id", "total", "paid"]
    assert len(rows) == 2


def test_sample_table_rejects_bad_identifier(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    with pytest.raises(ValueError):
        sample_table(db, "shop", "ord;DROP", limit=10)
