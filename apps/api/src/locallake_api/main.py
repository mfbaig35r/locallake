# SPDX-License-Identifier: Apache-2.0
"""LocalLake FastAPI app — Phase 0 skeleton.

Only ``/health`` exists. Routes for /jobs, /notebooks, /sql, /catalog,
/git, /schedules land in subsequent phases.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="LocalLake API", version="0.0.1")

_origins = os.environ.get("LOCALLAKE_CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "locallake-api", "version": "0.0.1"}
