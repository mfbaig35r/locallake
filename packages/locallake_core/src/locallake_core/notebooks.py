# SPDX-License-Identifier: Apache-2.0
"""Filesystem-backed notebook discovery.

Notebooks live under ``cfg.paths.notebooks`` as ``.py`` marimo files. We don't
cache anything in SQLite — the directory is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from locallake_core.config import LakehouseConfig


@dataclass
class NotebookEntry:
    """A discovered notebook file, relative to the workspace notebooks dir."""

    path: str  # workspace-relative
    name: str
    size_bytes: int
    last_modified: datetime


def list_notebooks(cfg: LakehouseConfig) -> list[NotebookEntry]:
    """Recursively list ``.py`` files under ``cfg.paths.notebooks``."""
    root = Path(cfg.paths.notebooks).resolve()
    if not root.exists():
        return []

    entries: list[NotebookEntry] = []
    for f in sorted(root.rglob("*.py")):
        if not f.is_file():
            continue
        rel = f.relative_to(root)
        stat = f.stat()
        entries.append(
            NotebookEntry(
                path=str(rel),
                name=f.name,
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )
    return entries
