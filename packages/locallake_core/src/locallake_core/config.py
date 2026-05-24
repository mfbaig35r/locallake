# SPDX-License-Identifier: Apache-2.0
"""Workspace configuration loader.

Reads ``config/workspace.yaml`` into a pydantic model. Paths in the YAML are
always absolute — when running under Docker they're container paths, mapped
from host paths via compose volumes. The validator rejects relative paths to
surface this distinction at load time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class DatabaseConfig(BaseModel):
    type: Literal["duckdb"] = "duckdb"
    path: str = Field(..., description="Absolute path to the DuckDB file")


class PathsConfig(BaseModel):
    notebooks: str
    artifacts: str
    logs: str
    templates: str


class WorkspaceMeta(BaseModel):
    name: str
    root_path: str


class LakehouseConfig(BaseModel):
    workspace: WorkspaceMeta
    database: DatabaseConfig
    paths: PathsConfig

    @model_validator(mode="after")
    def _absolute_paths(self) -> LakehouseConfig:
        def _check(label: str, value: str) -> None:
            if not Path(value).is_absolute():
                raise ValueError(
                    f"{label} must be an absolute path (got {value!r}). "
                    "Use container paths when running under Docker."
                )

        _check("workspace.root_path", self.workspace.root_path)
        _check("database.path", self.database.path)
        _check("paths.notebooks", self.paths.notebooks)
        _check("paths.artifacts", self.paths.artifacts)
        _check("paths.logs", self.paths.logs)
        _check("paths.templates", self.paths.templates)
        return self

    @classmethod
    def from_file(cls, path: str | Path) -> LakehouseConfig:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def to_file(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.model_dump(), sort_keys=False), encoding="utf-8")
