# SPDX-License-Identifier: Apache-2.0
"""Notebook template listing + create-from-template helper.

Templates live in ``cfg.paths.templates``. The CLI's ``lake init`` copies
the package-bundled defaults there on first run, but the directory is
user-editable — anything they drop in ``workspace/templates/*.py`` is a
valid template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from locallake_core.config import LakehouseConfig

# Identifier-ish filenames: letters, digits, underscores, dashes, periods,
# plus mandatory ``.py`` suffix. Forbids path separators and traversal.
_VALID_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]*\.py$")


class TemplateNotFoundError(Exception):
    """The requested template name doesn't exist."""


class InvalidNotebookNameError(ValueError):
    """The requested new-notebook name failed the safety check."""


class NotebookAlreadyExistsError(FileExistsError):
    """A notebook with the requested name already exists."""


@dataclass
class TemplateEntry:
    name: str
    size_bytes: int
    last_modified: datetime


def list_templates(cfg: LakehouseConfig) -> list[TemplateEntry]:
    """Return every ``*.py`` under ``cfg.paths.templates``."""
    root = Path(cfg.paths.templates)
    if not root.is_dir():
        return []
    out: list[TemplateEntry] = []
    for entry in sorted(root.glob("*.py")):
        if not entry.is_file():
            continue
        stat = entry.stat()
        out.append(
            TemplateEntry(
                name=entry.name,
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )
    return out


def validate_notebook_name(name: str) -> str:
    """Reject names with separators, traversal, or weird characters."""
    if not _VALID_NAME.match(name):
        raise InvalidNotebookNameError(f"notebook name must look like '<word>.py' (got {name!r})")
    return name


def create_from_template(
    cfg: LakehouseConfig,
    *,
    template: str,
    name: str,
) -> Path:
    """Copy ``cfg.paths.templates/<template>`` to ``cfg.paths.notebooks/<name>``.

    Returns the destination path. Raises ``TemplateNotFoundError`` if the
    source template is missing, ``NotebookAlreadyExistsError`` if the target
    file exists, and ``InvalidNotebookNameError`` for unsafe names.
    """
    validate_notebook_name(template)
    validate_notebook_name(name)

    src = Path(cfg.paths.templates) / template
    if not src.is_file():
        raise TemplateNotFoundError(f"template not found: {template}")

    dst = Path(cfg.paths.notebooks) / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise NotebookAlreadyExistsError(f"notebook already exists: {name}")

    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst
