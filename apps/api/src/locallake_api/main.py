# SPDX-License-Identifier: Apache-2.0
"""LocalLake FastAPI app.

Phase 1: ``/health`` plus ``/notebooks/{path:path}/run`` and ``/jobs/*``.
The Redis pool for arq enqueueing is created on startup and torn down on
shutdown via the lifespan context.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from locallake_core.migrations import run_migrations

from locallake_api import websocket
from locallake_api.routes import (
    artifacts,
    catalog,
    git,
    jobs,
    notebooks,
    sql,
    templates,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Bring the metadata DB to head before accepting traffic. Idempotent.
    run_migrations()

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    app.state.redis = pool
    logger.info("redis pool ready (%s)", redis_url)
    try:
        yield
    finally:
        await pool.aclose()
        logger.info("redis pool closed")


app = FastAPI(title="LocalLake API", version="0.0.1", lifespan=lifespan)

_origins = os.environ.get("LOCALLAKE_CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notebooks.router)
app.include_router(templates.router)
app.include_router(jobs.router)
app.include_router(artifacts.router)
app.include_router(sql.router)
app.include_router(catalog.router)
app.include_router(git.router)
app.include_router(websocket.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "locallake-api", "version": "0.0.1"}
