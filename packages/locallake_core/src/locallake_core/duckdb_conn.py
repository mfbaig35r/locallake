# SPDX-License-Identifier: Apache-2.0
"""DuckDB connection helpers — short-lived connections + retry on file lock.

Three processes touch the workspace DuckDB file: the API (read-only via the SQL
page), the worker (held for the duration of a notebook run), and the notebook
subprocess itself. DuckDB enforces one writer per file across processes, so the
brief windows when another process holds the lock surface as ``IOException``.
Bounded exponential backoff covers the common case where another process is
just finishing up.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_LOCK_RETRY_ATTEMPTS = 5
_LOCK_RETRY_BASE_DELAY = 0.05  # exponential — total ≈ 750 ms across 5 tries


def expand_db_path(db_path: str) -> str:
    """Expand ``~`` and ensure parent dir exists; pass through ``:memory:``."""
    if db_path == ":memory:":
        return db_path
    expanded = str(Path(db_path).expanduser().resolve())
    Path(expanded).parent.mkdir(parents=True, exist_ok=True)
    return expanded


def connect_with_retry(db_path: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB file with bounded retry on cross-process lock contention."""
    last_exc: duckdb.IOException | None = None
    for attempt in range(_LOCK_RETRY_ATTEMPTS):
        try:
            return duckdb.connect(db_path, read_only=read_only)
        except duckdb.IOException as exc:
            last_exc = exc
            if attempt == _LOCK_RETRY_ATTEMPTS - 1:
                break
            time.sleep(_LOCK_RETRY_BASE_DELAY * (2**attempt))
    assert last_exc is not None
    raise last_exc


class DuckDBPool:
    """Per-process connection lifecycle.

    File-backed: open fresh per ``scope()`` call, close on exit so the file lock
    is released the moment the operation ends. ``:memory:`` keeps a persistent
    connection because closing would lose state.
    """

    def __init__(self, db_path: str, read_only: bool = False) -> None:
        self._db_path = expand_db_path(db_path)
        self._read_only = read_only
        self._in_memory = self._db_path == ":memory:"
        self._memory_conn: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()

    @contextmanager
    def scope(self) -> Iterator[duckdb.DuckDBPyConnection]:
        if self._in_memory:
            with self._lock:
                if self._memory_conn is None:
                    self._memory_conn = duckdb.connect(self._db_path, read_only=self._read_only)
            yield self._memory_conn
            return

        conn = connect_with_retry(self._db_path, read_only=self._read_only)
        try:
            yield conn
        finally:
            conn.close()
