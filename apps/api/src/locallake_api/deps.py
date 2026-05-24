# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependency providers.

Three things flow through Depends():
- ``LakehouseConfig`` — workspace.yaml, cached for process lifetime
- session factory — SQLite session maker for metadata
- arq pool — Redis connection for enqueueing notebook jobs

The redis pool is created at app startup via the lifespan context and lives
on ``app.state``. Config and session factory are simple lru_cache singletons.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, Request
from locallake_core.config import LakehouseConfig
from locallake_core.db import make_session_factory
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def get_config() -> LakehouseConfig:
    path = os.environ.get("LOCALLAKE_CONFIG", "config/workspace.yaml")
    return LakehouseConfig.from_file(path)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory()


def get_redis_pool(request: Request) -> Any:
    pool = getattr(request.app.state, "redis", None)
    if pool is None:
        raise HTTPException(503, "redis pool not initialized")
    return pool


def get_marimo_sessions(request: Request) -> Any:
    sessions = getattr(request.app.state, "marimo_sessions", None)
    if sessions is None:
        raise HTTPException(503, "marimo session manager not initialized")
    return sessions
