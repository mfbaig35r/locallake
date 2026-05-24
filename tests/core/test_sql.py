# SPDX-License-Identifier: Apache-2.0
"""SQL query runner — allowlist, read-only, row cap, timeout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest
from locallake_core.sql import (
    SqlTimeoutError,
    SqlValidationError,
    run_query,
    validate_select_only,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  select 1 ",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SHOW TABLES",
        "DESCRIBE information_schema.tables",
        "EXPLAIN SELECT 1",
    ],
)
def test_validate_accepts_read_statements(sql: str) -> None:
    validate_select_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "DELETE FROM t",
        "UPDATE t SET x=1",
        "DROP TABLE t",
        "CREATE TABLE t (x INT)",
        "ATTACH ':memory:'",
        "PRAGMA memory_limit='2GB'",
        "",
        "   ",
    ],
)
def test_validate_rejects_mutating_or_empty(sql: str) -> None:
    with pytest.raises(SqlValidationError):
        validate_select_only(sql)


def test_validate_rejects_multiple_statements() -> None:
    with pytest.raises(SqlValidationError):
        validate_select_only("SELECT 1; SELECT 2")


def test_validate_allows_semicolon_in_string_literal() -> None:
    validate_select_only("SELECT ';' AS x")


def test_run_query_basic(tmp_path: Path) -> None:
    db = tmp_path / "x.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("CREATE TABLE t(id INTEGER, name TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'a'), (2, 'b'), (3, 'c')")
    conn.close()

    result = run_query(str(db), "SELECT * FROM t ORDER BY id")
    assert result.columns == ["id", "name"]
    assert result.rows == [[1, "a"], [2, "b"], [3, "c"]]
    assert result.row_count == 3
    assert result.truncated is False


def test_run_query_creates_db_if_missing(tmp_path: Path) -> None:
    db = tmp_path / "nope.duckdb"
    assert not db.exists()
    result = run_query(str(db), "SELECT 1 AS one")
    assert result.rows == [[1]]
    assert db.exists()


def test_run_query_row_limit_truncates(tmp_path: Path) -> None:
    db = tmp_path / "y.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("CREATE TABLE t AS SELECT * FROM range(100) t(x)")
    conn.close()

    result = run_query(str(db), "SELECT * FROM t", row_limit=10)
    assert len(result.rows) == 10
    assert result.row_count == 10
    assert result.truncated is True


def test_run_query_rejects_write(tmp_path: Path) -> None:
    db = tmp_path / "z.duckdb"
    with pytest.raises(SqlValidationError):
        run_query(str(db), "CREATE TABLE t(x INT)")


def test_run_query_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the timer→interrupt path raises SqlTimeoutError.

    Real wall-clock timeouts are flaky in CI because DuckDB optimises most
    "obvious" slow queries. We instead start a query and fire the timer's
    callback immediately from a sidecar thread — same code path the runner
    exercises in production.
    """
    import threading

    real_timer_cls = threading.Timer
    fired = threading.Event()

    class ImmediateTimer:
        def __init__(self, interval: float, fn: Any) -> None:
            self._fn = fn

        def start(self) -> None:
            # Fire on a background thread so the main thread is mid-query.
            real_timer_cls(0.05, self._fire).start()

        def _fire(self) -> None:
            try:
                self._fn()
            finally:
                fired.set()

        def cancel(self) -> None:
            pass

    monkeypatch.setattr("locallake_core.sql.threading.Timer", ImmediateTimer)

    db = tmp_path / "slow.duckdb"
    # Cross product that takes long enough for the 50 ms timer to land first.
    with pytest.raises(SqlTimeoutError):
        run_query(
            str(db),
            "SELECT COUNT(*) FROM range(2_000_000) a, range(200) b WHERE a.range > b.range",
            timeout_seconds=5,
        )
    assert fired.is_set()
