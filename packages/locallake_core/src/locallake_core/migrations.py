# SPDX-License-Identifier: Apache-2.0
"""Programmatic Alembic runner — used by the API on startup.

Alembic itself is fine, but driving it via the ``alembic`` CLI inside Docker
means an extra shell script + an extra subprocess on every container start.
This module wraps ``command.upgrade(cfg, "head")`` so the API's FastAPI
lifespan can do the same thing in-process. Idempotent: if the DB is already
at head, this is a no-op apart from the version-table SELECT.

Layout assumption (holds for both editable and Docker installs):
    packages/locallake_core/
        alembic.ini
        alembic/
            env.py
            versions/...
        src/
            locallake_core/        <- this file
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def _package_root() -> Path:
    """Return ``packages/locallake_core/`` regardless of install mode."""
    # __file__ -> packages/locallake_core/src/locallake_core/migrations.py
    return Path(__file__).resolve().parent.parent.parent


def _alembic_config() -> Config:
    root = _package_root()
    alembic_dir = root / "alembic"
    if not alembic_dir.is_dir():
        raise RuntimeError(
            f"alembic directory not found at {alembic_dir}; "
            "is locallake-core installed as a wheel without bundled migrations?"
        )
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    # Match what alembic.ini sets for the on-disk equivalent.
    cfg.set_main_option("prepend_sys_path", str(root / "src"))
    return cfg


def run_migrations() -> None:
    """Bring the metadata DB up to head. Reads ``LOCALLAKE_METADATA_DB``."""
    cfg = _alembic_config()
    logger.info("running alembic upgrade head")
    command.upgrade(cfg, "head")
