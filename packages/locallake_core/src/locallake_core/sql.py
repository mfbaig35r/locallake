# SPDX-License-Identifier: Apache-2.0
"""Read-only SQL query runner backed by DuckDB.

Three layers of protection against destructive statements:

1. ``duckdb.connect(path, read_only=True)`` — DuckDB refuses writes.
2. Statement-prefix allowlist — only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN are
   accepted by the ``/sql/query`` endpoint. PRAGMA values that mutate engine
   state are denied; read-only PRAGMAs (``SELECT * FROM pragma_*``) flow
   through the SELECT path anyway.
3. Single-statement enforcement — multiple statements separated by ``;``
   outside string literals are rejected.

Query execution runs on a worker thread with a ``threading.Timer`` that calls
``conn.interrupt()`` once ``timeout_seconds`` elapses. Memory cap is applied
via ``PRAGMA memory_limit`` on the connection.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


# Prefix allowlist for ``/sql/query``. Anchored at the start of the trimmed
# query. PRAGMA is excluded intentionally — read introspection happens via
# ``SELECT FROM duckdb_*`` / ``SHOW`` instead, which can't toggle engine state.
_ALLOWED_PREFIX = re.compile(
    r"^\s*(SELECT|WITH|SHOW|DESCRIBE|DESC|EXPLAIN)\b",
    re.IGNORECASE,
)

# Default per-connection caps. Overridable per request up to the hard caps
# in the API layer.
DEFAULT_TIMEOUT_S = 30
DEFAULT_ROW_LIMIT = 10_000
DEFAULT_MEMORY_LIMIT = "1GB"


class SqlValidationError(ValueError):
    """Statement rejected before execution (allowlist or multi-statement)."""


class SqlTimeoutError(RuntimeError):
    """Query exceeded ``timeout_seconds`` and was interrupted."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int


def validate_select_only(sql: str) -> None:
    """Raise ``SqlValidationError`` for anything outside the read allowlist."""
    stripped = sql.strip()
    if not stripped:
        raise SqlValidationError("query is empty")
    if not _ALLOWED_PREFIX.match(stripped):
        raise SqlValidationError("only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN queries are allowed")
    if _has_multiple_statements(stripped):
        raise SqlValidationError(
            "multiple statements per query are not supported; submit one at a time"
        )


def _has_multiple_statements(sql: str) -> bool:
    """Detect ``;`` outside string literals — DuckDB allows multi-statement.

    Walks the string tracking single and double-quote state; backslash escapes
    are NOT honored (DuckDB SQL uses doubled quotes to escape).
    """
    in_single = False
    in_double = False
    rest = sql.rstrip().rstrip(";")
    for ch in rest:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            return True
    return False


def _ensure_db_exists(db_path: str) -> None:
    """Create the DuckDB file if absent so ``read_only=True`` can open it."""
    if db_path == ":memory:":
        return
    expanded = Path(db_path).expanduser().resolve()
    expanded.parent.mkdir(parents=True, exist_ok=True)
    if expanded.exists():
        return
    # Touch the file by opening a write connection and closing immediately.
    conn = duckdb.connect(str(expanded), read_only=False)
    conn.close()


def run_query(
    db_path: str,
    sql: str,
    *,
    row_limit: int = DEFAULT_ROW_LIMIT,
    timeout_seconds: int = DEFAULT_TIMEOUT_S,
    memory_limit: str = DEFAULT_MEMORY_LIMIT,
) -> QueryResult:
    """Validate + execute a read-only query, honoring row + time caps."""
    validate_select_only(sql)
    _ensure_db_exists(db_path)

    conn = duckdb.connect(_expand(db_path), read_only=True)
    timer: threading.Timer | None = None
    timed_out = threading.Event()

    def _interrupt() -> None:
        timed_out.set()
        try:
            conn.interrupt()
        except Exception:
            # interrupt() is best-effort; if the conn is already closed we
            # raise below from the resulting exception.
            logger.exception("conn.interrupt() raised")

    try:
        # Soft memory cap. DuckDB throws if the limit value is malformed; we
        # let that surface as a 422 to the caller.
        conn.execute(f"SET memory_limit='{_escape_pragma(memory_limit)}'")
        if timeout_seconds > 0:
            timer = threading.Timer(timeout_seconds, _interrupt)
            timer.start()
        start = time.monotonic()
        cur = conn.execute(sql)
        # Fetch one row past the limit so we can mark truncation accurately.
        sample = cur.fetchmany(row_limit + 1)
        duration_ms = int((time.monotonic() - start) * 1000)
        columns = [c[0] for c in cur.description] if cur.description else []
        truncated = len(sample) > row_limit
        rows = sample[:row_limit]
        serialized = [[_jsonable(v) for v in row] for row in rows]
        return QueryResult(
            columns=columns,
            rows=serialized,
            row_count=len(rows),
            truncated=truncated,
            duration_ms=duration_ms,
        )
    except duckdb.Error as exc:
        if timed_out.is_set():
            raise SqlTimeoutError(f"query exceeded {timeout_seconds}s timeout") from exc
        raise
    finally:
        if timer is not None:
            timer.cancel()
        conn.close()


def _expand(db_path: str) -> str:
    if db_path == ":memory:":
        return db_path
    return str(Path(db_path).expanduser().resolve())


def _escape_pragma(value: str) -> str:
    """Sanitize a PRAGMA value — only word chars + simple suffixes allowed."""
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", value):
        raise SqlValidationError(f"invalid pragma value: {value!r}")
    return value


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | float | str):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)
