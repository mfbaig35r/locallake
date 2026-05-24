# SPDX-License-Identifier: Apache-2.0
"""schedule max_retries

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.add_column(
            sa.Column(
                "max_retries",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.drop_column("max_retries")
