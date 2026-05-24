# SPDX-License-Identifier: Apache-2.0
"""/templates, POST /notebooks, /git/* endpoints."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from locallake_core.config import LakehouseConfig


def _seed_templates(cfg: LakehouseConfig, *names: str) -> None:
    root = Path(cfg.paths.templates)
    root.mkdir(parents=True, exist_ok=True)
    for n in names:
        (root / n).write_text(f"# template {n}\n")


def test_list_templates(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_templates(lake_config, "hello.py", "demo.py")
    res = client.get("/templates")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert sorted(t["name"] for t in body["items"]) == ["demo.py", "hello.py"]


def test_create_notebook_from_template(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_templates(lake_config, "hello.py")
    res = client.post(
        "/notebooks",
        json={"template": "hello.py", "name": "my_first.py"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["path"] == "my_first.py"
    assert (Path(lake_config.paths.notebooks) / "my_first.py").is_file()


def test_create_notebook_404_for_missing_template(
    client: Any, lake_config: LakehouseConfig
) -> None:
    res = client.post("/notebooks", json={"template": "missing.py", "name": "x.py"})
    assert res.status_code == 404


def test_create_notebook_409_when_exists(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_templates(lake_config, "hello.py")
    (Path(lake_config.paths.notebooks) / "dup.py").write_text("# already")
    res = client.post("/notebooks", json={"template": "hello.py", "name": "dup.py"})
    assert res.status_code == 409


def test_create_notebook_400_for_unsafe_name(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_templates(lake_config, "hello.py")
    res = client.post("/notebooks", json={"template": "hello.py", "name": "../escape.py"})
    assert res.status_code == 400


def test_git_status_for_non_repo(client: Any) -> None:
    res = client.get("/git/status")
    assert res.status_code == 200
    body = res.json()
    assert body["is_repo"] is False
    assert body["branch"] is None


def test_git_status_and_log_for_repo(client: Any, lake_config: LakehouseConfig) -> None:
    repo = Path(lake_config.workspace.root_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)

    status = client.get("/git/status").json()
    assert status["is_repo"] is True
    assert status["branch"] == "main"
    assert status["dirty"] is False
    assert isinstance(status["commit_sha"], str)

    log = client.get("/git/log?limit=5").json()
    assert log["total"] == 1
    assert log["items"][0]["message"] == "initial"
