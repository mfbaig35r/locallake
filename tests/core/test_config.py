# SPDX-License-Identifier: Apache-2.0
"""Workspace config loader smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from locallake_core.config import LakehouseConfig


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "workspace.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _valid_data() -> dict:
    return {
        "workspace": {"name": "test", "root_path": "/workspace"},
        "database": {"type": "duckdb", "path": "/data/test.duckdb"},
        "paths": {
            "notebooks": "/workspace/notebooks",
            "artifacts": "/workspace/artifacts",
            "logs": "/workspace/logs",
            "templates": "/workspace/templates",
        },
    }


def test_loads_valid_config(tmp_path: Path) -> None:
    p = _write(tmp_path, _valid_data())
    cfg = LakehouseConfig.from_file(p)
    assert cfg.workspace.name == "test"
    assert cfg.database.path == "/data/test.duckdb"
    assert cfg.paths.notebooks == "/workspace/notebooks"


def test_rejects_relative_root(tmp_path: Path) -> None:
    data = _valid_data()
    data["workspace"]["root_path"] = "./workspace"
    p = _write(tmp_path, data)
    with pytest.raises(ValueError, match="absolute"):
        LakehouseConfig.from_file(p)


def test_rejects_relative_db_path(tmp_path: Path) -> None:
    data = _valid_data()
    data["database"]["path"] = "data/local.duckdb"
    p = _write(tmp_path, data)
    with pytest.raises(ValueError, match="absolute"):
        LakehouseConfig.from_file(p)


def test_roundtrip(tmp_path: Path) -> None:
    p = _write(tmp_path, _valid_data())
    cfg = LakehouseConfig.from_file(p)
    out = tmp_path / "out.yaml"
    cfg.to_file(out)
    cfg2 = LakehouseConfig.from_file(out)
    assert cfg.model_dump() == cfg2.model_dump()
