# SPDX-License-Identifier: Apache-2.0
"""Shared API test fixtures.

We sidestep the FastAPI lifespan (which would try to connect to a real Redis)
by overriding the three Depends() providers — config, session_factory, redis
pool — on the FastAPI app object directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from locallake_api.deps import get_config, get_redis_pool, get_session_factory
from locallake_api.main import app
from locallake_core.config import (
    DatabaseConfig,
    LakehouseConfig,
    PathsConfig,
    WorkspaceMeta,
)
from locallake_core.db import make_session_factory
from locallake_core.models import Base


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    for sub in ("notebooks", "artifacts", "logs", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def lake_config(workspace_dir: Path) -> LakehouseConfig:
    root = workspace_dir / "workspace"
    return LakehouseConfig(
        workspace=WorkspaceMeta(name="t", root_path=str(root)),
        database=DatabaseConfig(type="duckdb", path=str(workspace_dir / "data" / "x.duckdb")),
        paths=PathsConfig(
            notebooks=str(root / "notebooks"),
            artifacts=str(root / "artifacts"),
            logs=str(root / "logs"),
            templates=str(root / "templates"),
        ),
    )


@pytest.fixture
def session_factory(workspace_dir: Path) -> Any:
    factory = make_session_factory(str(workspace_dir / "meta.sqlite"))
    Base.metadata.create_all(factory.kw["bind"])
    return factory


@pytest.fixture
def mock_pool() -> Any:
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    return pool


@pytest.fixture
def client(
    lake_config: LakehouseConfig,
    session_factory: Any,
    mock_pool: Any,
) -> Any:
    # Don't use `with TestClient(...)` — that invokes the lifespan, which would
    # try to open a real Redis connection. Dependency overrides cover what
    # lifespan would normally provide.
    app.dependency_overrides[get_config] = lambda: lake_config
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_redis_pool] = lambda: mock_pool
    yield TestClient(app)
    app.dependency_overrides.clear()
