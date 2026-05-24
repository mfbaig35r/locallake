# SPDX-License-Identifier: Apache-2.0
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("notebook_path", sa.String(1024), nullable=False),
        sa.Column("cron_expression", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("last_run_at", sa.DateTime, nullable=True),
        sa.Column("last_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("parameters_json", sa.Text, nullable=False, server_default="{}"),
    )
    op.create_index("ix_schedules_enabled", "schedules", ["enabled"])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("notebook_path", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("triggered_by", sa.String(32), nullable=False),
        sa.Column("git_commit_sha", sa.String(40), nullable=True),
        sa.Column("git_dirty", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("log_path", sa.String(1024), nullable=True),
        sa.Column("artifact_path", sa.String(1024), nullable=True),
        sa.Column("mcp_run_id", sa.String(64), nullable=True),
        sa.Column("parameters_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column(
            "parent_run_id",
            sa.String(36),
            sa.ForeignKey("job_runs.id"),
            nullable=True,
        ),
        sa.Column(
            "schedule_id",
            sa.String(36),
            sa.ForeignKey("schedules.id"),
            nullable=True,
        ),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="300"),
    )
    op.create_index("ix_job_runs_status", "job_runs", ["status"])
    op.create_index("ix_job_runs_created_at", "job_runs", ["created_at"])

    op.create_table(
        "saved_queries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, unique=True),
        sa.Column("sql", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "query_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sql", sa.Text, nullable=False),
        sa.Column("executed_at", sa.DateTime, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_query_history_executed_at", "query_history", ["executed_at"])


def downgrade() -> None:
    op.drop_index("ix_query_history_executed_at", table_name="query_history")
    op.drop_table("query_history")
    op.drop_table("saved_queries")
    op.drop_index("ix_job_runs_created_at", table_name="job_runs")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index("ix_schedules_enabled", table_name="schedules")
    op.drop_table("schedules")
