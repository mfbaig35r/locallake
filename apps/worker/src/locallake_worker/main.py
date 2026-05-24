# SPDX-License-Identifier: Apache-2.0
"""LocalLake arq worker — Phase 0 skeleton.

Only a ``ping`` task. Real ``run_notebook`` task lands in Phase 1.
Start with: ``arq locallake_worker.main.WorkerSettings``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def ping(_ctx: dict[str, Any], *, msg: str = "hello") -> str:
    """Placeholder task — proves the worker is wired up."""
    logger.info("ping: %s", msg)
    return msg


def _redis_settings() -> RedisSettings:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    functions = [ping]
    redis_settings = _redis_settings()
    job_timeout = 3600
    max_jobs = int(os.environ.get("LOCALLAKE_WORKER_CONCURRENCY", "2"))
