# region __lake__ context (injected by LocalLake notebook tools)
# This file is read as a string at runtime and prepended to user code in a
# marimo-sandbox subprocess. It is NOT imported by the locallake_core package
# itself.
# Source: locallake_core/context_template.py
#
# All imports are aliased with _lake_ prefix to minimize namespace pollution.
# Do not add locallake_core.* imports — the package is not installed in the
# notebook venv. The notebook venv only has marimo + duckdb + (optionally) the
# `locallake` shim, but since we register `locallake` in sys.modules below, the
# shim is not actually required either.
import json as _lake_json
import os as _lake_os
import sys as _lake_sys
import time as _lake_time
import types as _lake_types
from pathlib import Path as _lake_Path
from typing import Any as _lake_Any


def _lake_connect_duckdb_with_retry(_ddb, db_path: str, read_only: bool = False):
    """Open a DuckDB file with bounded retry on cross-process lock contention.

    Mirrors the server-side retry in locallake_core/duckdb_conn.py so that
    notebook subprocesses tolerate the brief window when another process
    (the API's SQL page, another worker job) holds the file lock.
    """
    last_exc = None
    for attempt in range(5):
        try:
            return _ddb.connect(db_path, read_only=read_only)
        except _ddb.IOException as exc:
            last_exc = exc
            if attempt == 4:
                break
            _lake_time.sleep(0.05 * (2**attempt))
    raise last_exc


class _LakeContext:
    """LocalLake notebook context.

    Reconstructs the configured DuckDB connection + workspace paths from
    LOCALLAKE_* env variables inherited from the parent worker process.

    Credentials note: this object inherits the worker process environment.
    Anyone with shell access to a process started with the same env can use
    those values. The saved .py notebook on disk contains no env vars, but
    its inputs (the user's code) and outputs (artifacts) do live on disk.
    """

    def __init__(self) -> None:
        self._conn: _lake_Any = None
        self._db_path = _lake_os.environ["LOCALLAKE_DB_PATH"]
        self._workspace_path = _lake_os.environ["LOCALLAKE_WORKSPACE_PATH"]
        self._artifacts_dir = _lake_os.environ["LOCALLAKE_RUN_ARTIFACTS_DIR"]
        self._log_path = _lake_os.environ["LOCALLAKE_RUN_LOG_PATH"]
        self._params = _lake_json.loads(_lake_os.environ.get("LOCALLAKE_RUN_PARAMS", "{}"))

    def connection(self) -> _lake_Any:
        """Return a (cached) DuckDB connection to the workspace database."""
        if self._conn is not None:
            return self._conn
        import duckdb as _ddb

        expanded = str(_lake_Path(self._db_path).expanduser().resolve())
        _lake_Path(expanded).parent.mkdir(parents=True, exist_ok=True)
        self._conn = _lake_connect_duckdb_with_retry(_ddb, expanded)
        return self._conn

    def workspace(self) -> str:
        """Absolute path to the workspace root."""
        return self._workspace_path

    def artifacts_dir(self) -> str:
        """Absolute path to this run's artifacts directory (created on demand)."""
        _lake_Path(self._artifacts_dir).mkdir(parents=True, exist_ok=True)
        return self._artifacts_dir

    def save_artifact(self, name: str, data: bytes | str) -> str:
        """Persist an artifact under the run's artifacts dir; returns full path."""
        path = _lake_Path(self._artifacts_dir) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return str(path)

    def log(self, msg: str, level: str = "info") -> None:
        """Append a timestamped line to this run's log file."""
        ts = _lake_time.strftime("%Y-%m-%dT%H:%M:%S")
        line = f"{ts} [{level}] {msg}\n"
        _lake_Path(self._log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def parameters(self) -> dict:
        """Return a copy of the parameters passed to this run."""
        return dict(self._params)


__lake__ = _LakeContext()

# Expose `locallake` as a synthetic module so notebooks can write
# `from locallake import get_connection` without the pip package being
# installed in the notebook venv. The shim package on PyPI does exactly the
# same thing via builtins; this just covers the no-PyPI case.
_lake_mod = _lake_types.ModuleType("locallake")
_lake_mod.get_connection = __lake__.connection  # type: ignore[attr-defined]
_lake_mod.workspace = __lake__.workspace  # type: ignore[attr-defined]
_lake_mod.artifacts_dir = __lake__.artifacts_dir  # type: ignore[attr-defined]
_lake_mod.save_artifact = __lake__.save_artifact  # type: ignore[attr-defined]
_lake_mod.log = __lake__.log  # type: ignore[attr-defined]
_lake_mod.parameters = __lake__.parameters  # type: ignore[attr-defined]
_lake_sys.modules["locallake"] = _lake_mod
# endregion __lake__ context
