# SPDX-License-Identifier: Apache-2.0
"""Template listing + create-from-template safety."""

from __future__ import annotations

from pathlib import Path

import pytest
from locallake_core.config import (
    DatabaseConfig,
    LakehouseConfig,
    PathsConfig,
    WorkspaceMeta,
)
from locallake_core.templates import (
    InvalidNotebookNameError,
    NotebookAlreadyExistsError,
    TemplateNotFoundError,
    create_from_template,
    list_templates,
    validate_notebook_name,
)


def _cfg(tmp_path: Path) -> LakehouseConfig:
    root = tmp_path / "workspace"
    for sub in ("notebooks", "artifacts", "logs", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return LakehouseConfig(
        workspace=WorkspaceMeta(name="t", root_path=str(root)),
        database=DatabaseConfig(type="duckdb", path=str(tmp_path / "data" / "x.duckdb")),
        paths=PathsConfig(
            notebooks=str(root / "notebooks"),
            artifacts=str(root / "artifacts"),
            logs=str(root / "logs"),
            templates=str(root / "templates"),
        ),
    )


def test_list_templates_empty(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    assert list_templates(cfg) == []


def test_list_templates_returns_py_files(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (Path(cfg.paths.templates) / "hello.py").write_text("# hi")
    (Path(cfg.paths.templates) / "demo.py").write_text("# demo")
    (Path(cfg.paths.templates) / "README.md").write_text("ignored")
    items = list_templates(cfg)
    assert sorted(t.name for t in items) == ["demo.py", "hello.py"]


@pytest.mark.parametrize(
    "name",
    ["a/b.py", "../escape.py", ".hidden.py", "no_suffix", "weird.txt", "../../etc/passwd"],
)
def test_validate_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(InvalidNotebookNameError):
        validate_notebook_name(name)


def test_create_from_template_writes_destination(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (Path(cfg.paths.templates) / "hello.py").write_text("# template body\n")
    dst = create_from_template(cfg, template="hello.py", name="my_first.py")
    assert dst.read_text(encoding="utf-8") == "# template body\n"
    assert dst.parent == Path(cfg.paths.notebooks)


def test_create_from_template_404_for_missing(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    with pytest.raises(TemplateNotFoundError):
        create_from_template(cfg, template="missing.py", name="ok.py")


def test_create_from_template_409_when_exists(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (Path(cfg.paths.templates) / "hello.py").write_text("# t")
    (Path(cfg.paths.notebooks) / "existing.py").write_text("# already here")
    with pytest.raises(NotebookAlreadyExistsError):
        create_from_template(cfg, template="hello.py", name="existing.py")


def test_create_from_template_rejects_unsafe_target(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (Path(cfg.paths.templates) / "hello.py").write_text("# t")
    with pytest.raises(InvalidNotebookNameError):
        create_from_template(cfg, template="hello.py", name="../escape.py")
