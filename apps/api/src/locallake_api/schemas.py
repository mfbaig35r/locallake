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
