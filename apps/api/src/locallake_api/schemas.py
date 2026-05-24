# SPDX-License-Identifier: Apache-2.0
"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunNotebookRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    triggered_by: str = Field(default="api", max_length=32)


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_path: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    triggered_by: str
    git_commit_sha: str | None
    git_dirty: bool
    error_message: str | None
    log_path: str | None
    artifact_path: str | None
    mcp_run_id: str | None
    parameters_json: str
    parent_run_id: str | None
    schedule_id: str | None
    timeout_seconds: int


class JobListOut(BaseModel):
    items: list[JobRunOut]
    total: int
    limit: int
    offset: int


class CancelResponse(BaseModel):
    id: str
    status: str
    message: str


class NotebookEntryOut(BaseModel):
    path: str
    name: str
    size_bytes: int
    last_modified: datetime


class NotebookListOut(BaseModel):
    items: list[NotebookEntryOut]
    total: int


class NotebookDetailOut(BaseModel):
    path: str
    name: str
    size_bytes: int
    last_modified: datetime
    recent_runs: list[JobRunOut]


class ArtifactEntryOut(BaseModel):
    path: str
    size_bytes: int
    last_modified: datetime
    previewable: bool


class ArtifactListOut(BaseModel):
    items: list[ArtifactEntryOut]
    total: int


class ArtifactPreviewOut(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total_rows: int
    truncated: bool


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=200_000)
    row_limit: int = Field(default=1000, ge=1, le=10_000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class QueryResultOut(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int


class SavedQueryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    sql: str = Field(..., min_length=1, max_length=200_000)


class SavedQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    sql: str
    created_at: datetime
    updated_at: datetime


class SavedQueryListOut(BaseModel):
    items: list[SavedQueryOut]
    total: int


class QueryHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sql: str
    executed_at: datetime
    duration_ms: int
    row_count: int | None
    error_message: str | None


class QueryHistoryListOut(BaseModel):
    items: list[QueryHistoryOut]
    total: int


class TableEntryOut(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    kind: str
    model_config = ConfigDict(populate_by_name=True)


class TableListOut(BaseModel):
    items: list[TableEntryOut]
    total: int


class ColumnEntryOut(BaseModel):
    name: str
    type: str
    nullable: bool


class TableDetailOut(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    kind: str
    columns: list[ColumnEntryOut]
    row_count: int | None
    sample_columns: list[str]
    sample_rows: list[list[Any]]
    model_config = ConfigDict(populate_by_name=True)
