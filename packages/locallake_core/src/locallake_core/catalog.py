# SPDX-License-Identifier: Apache-2.0
"""DuckDB catalog introspection — schemas, tables, columns, samples.

All reads go through a fresh ``read_only=True`` connection so the API can
never accidentally mutate the user's database while browsing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import duckdb

from locallake_core.sql import _ensure_db_exists, _expand

logger = logging.getLogger(__name__)


@dataclass
class TableEntry:
    schema: str
    name: str
    kind: str  # 'table' or 'view'


@dataclass
class ColumnEntry:
    name: str
    type: str
    nullable: bool


@dataclass
class TableDetail:
    schema: str
    name: str
    kind: str
    columns: list[ColumnEntry]
    row_count: int | None


def _connect(db_path: str) -> duckdb.DuckDBPyConnection:
    _ensure_db_exists(db_path)
    return duckdb.connect(_expand(db_path), read_only=True)


def list_tables(db_path: str) -> list[TableEntry]:
    """Return all user tables + views, sorted (schema, name)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        TableEntry(
            schema=r[0],
            name=r[1],
            kind="view" if "VIEW" in (r[2] or "").upper() else "table",
        )
        for r in rows
    ]


def describe_table(db_path: str, schema: str, name: str) -> TableDetail | None:
    """Return columns + (best-effort) row count, or None if not found."""
    if not _ident(schema) or not _ident(name):
        raise ValueError("invalid schema/table identifier")
    conn = _connect(db_path)
    try:
        meta = conn.execute(
            """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema, name],
        ).fetchone()
        if meta is None:
            return None
        kind = "view" if "VIEW" in (meta[0] or "").upper() else "table"

        cols = conn.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [schema, name],
        ).fetchall()

        row_count: int | None
        try:
            row_count_row = conn.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}"').fetchone()
            row_count = int(row_count_row[0]) if row_count_row else None
        except duckdb.Error:
            row_count = None
    finally:
        conn.close()

    return TableDetail(
        schema=schema,
        name=name,
        kind=kind,
        columns=[
            ColumnEntry(
                name=c[0],
                type=c[1],
                nullable=(c[2] or "").upper() == "YES",
            )
            for c in cols
        ],
        row_count=row_count,
    )


def sample_table(
    db_path: str, schema: str, name: str, limit: int = 50
) -> tuple[list[str], list[list[Any]]]:
    """Return (columns, rows) for a small preview of the table."""
    if not _ident(schema) or not _ident(name):
        raise ValueError("invalid schema/table identifier")
    if limit < 1 or limit > 1_000:
        raise ValueError("limit must be between 1 and 1000")
    conn = _connect(db_path)
    try:
        cur = conn.execute(f'SELECT * FROM "{schema}"."{name}" LIMIT {int(limit)}')
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
    finally:
        conn.close()
    return cols, [list(r) for r in rows]


def _ident(s: str) -> bool:
    """Identifier safety — used as a defense-in-depth check before f-string
    interpolation. DuckDB still escapes via doubled-quotes; this just keeps
    obviously-malicious input from reaching the parser at all.
    """
    return bool(s) and all(c.isalnum() or c in "_-." for c in s) and len(s) < 128
