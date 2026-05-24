# SPDX-License-Identifier: Apache-2.0
"""LocalLake arq worker entry point.

One task — ``run_notebook(job_id)``. The workspace config and SQLAlchemy
session factory are loaded once at worker startup and stashed on the arq
context dict (``ctx``); the task itself just dispatches into
``locallake_worker.runner.execute_job``, run inside ``asyncio.to_thread``
because marimo-sandbox is blocking.

Start with: ``arq locallake_worker.main.WorkerSettings``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from arq.connections import RedisSettings
from locallake_core.config import LakehouseConfig
from locallake_core.db import make_session_factory

from locallake_worker.runner import execute_job

logger = logging.getLogger(__name__)


async def run_notebook(ctx: dict[str, Any], job_id: str) -> dict[str, Any]:
    cfg: LakehouseConfig = ctx["lake_config"]
    factory = ctx["session_factory"]
    return await asyncio.to_thread(execute_job, cfg, factory, job_id)


async def on_startup(ctx: dict[str, Any]) -> None:
    cfg_path = os.environ.get("LOCALLAKE_CONFIG", "config/workspace.yaml")
    ctx["lake_config"] = LakehouseConfig.from_file(cfg_path)
    ctx["session_factory"] = make_session_factory()
    logger.info("worker ready (config=%s, max_jobs=%s)", cfg_path, WorkerSettings.max_jobs)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker shutting down")


def _redis_settings() -> RedisSettings:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    functions = [run_notebook]
    redis_settings = _redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    job_timeout = 3600
    max_jobs = int(os.environ.get("LOCALLAKE_WORKER_CONCURRENCY", "2"))
