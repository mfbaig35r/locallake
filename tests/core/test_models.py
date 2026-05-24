# SPDX-License-Identifier: Apache-2.0
"""Smoke test for the SQLAlchemy metadata schema."""

from __future__ import annotations

from pathlib import Path

from locallake_core.db import make_engine
from locallake_core.models import Base
from sqlalchemy import inspect


def test_create_all_tables(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    engine = make_engine(str(db))
    Base.metadata.create_all(engine)

    insp = inspect(engine)
    table_names = set(insp.get_table_names())
    assert {"job_runs", "schedules", "saved_queries", "query_history"} <= table_names
