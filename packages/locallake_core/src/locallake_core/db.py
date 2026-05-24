# SPDX-License-Identifier: Apache-2.0
"""SQLite session factory with WAL mode + sensible pragmas.

The API process is the only writer; worker only reads. WAL lets the worker
read without blocking writers. ``check_same_thread=False`` is safe because
SQLAlchemy serializes access per-session.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_PATH = "./data/metadata.sqlite"


def _resolve_db_path(db_path: str | None = None) -> str:
    raw = db_path or os.environ.get("LOCALLAKE_METADATA_DB", DEFAULT_DB_PATH)
    p = Path(raw).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def make_engine(db_path: str | None = None) -> Engine:
    full_path = _resolve_db_path(db_path)
    engine = create_engine(
        f"sqlite:///{full_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _conn_record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def make_session_factory(db_path: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(db_path), expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
