# SPDX-License-Identifier: Apache-2.0
"""LocalLake notebook helper.

Thin shim — the actual implementation is injected into the notebook subprocess
at runtime as ``__lake__``. This package exists so notebook authors can write
``from locallake import get_connection`` instead of reaching for a builtin.

The injection lands in Phase 1; for now these helpers raise if called outside
a LocalLake notebook run.
"""

from __future__ import annotations

import builtins
from typing import Any, cast

__version__ = "0.0.1"


def _lake() -> Any:
    obj = getattr(builtins, "__lake__", None)
    if obj is None:
        raise RuntimeError(
            "locallake helpers are only available inside a notebook run "
            "(no __lake__ context found)."
        )
    return obj


def get_connection() -> Any:
    """Return a DuckDB connection to the configured workspace database."""
    return _lake().connection()


def workspace() -> str:
    """Return the workspace root path."""
    return cast(str, _lake().workspace())


def artifacts_dir() -> str:
    """Return this run's artifacts directory."""
    return cast(str, _lake().artifacts_dir())


def save_artifact(name: str, data: bytes | str) -> str:
    """Persist an artifact for this run; returns the path."""
    return cast(str, _lake().save_artifact(name, data))


def log(msg: str, level: str = "info") -> None:
    """Structured log line to this run's log file."""
    _lake().log(msg, level)


def parameters() -> dict[str, Any]:
    """Return the parameters passed to this run."""
    return cast(dict[str, Any], _lake().parameters())


__all__ = [
    "get_connection",
    "workspace",
    "artifacts_dir",
    "save_artifact",
    "log",
    "parameters",
]
