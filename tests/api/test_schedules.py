# SPDX-License-Identifier: Apache-2.0
"""/schedules CRUD endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from locallake_core.config import LakehouseConfig


def _seed_notebook(cfg: LakehouseConfig, name: str = "hello.py") -> None:
    nb = Path(cfg.paths.notebooks) / name
    nb.write_text("# nb\n")


def test_create_schedule(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    res = client.post(
        "/schedules",
        json={
            "notebook_path": "hello.py",
            "cron_expression": "0 * * * *",
            "parameters": {"k": "v"},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["notebook_path"] == "hello.py"
    assert body["cron_expression"] == "0 * * * *"
    assert body["enabled"] is True
    assert json.loads(body["parameters_json"]) == {"k": "v"}
    assert body["next_fire_at"] is not None


def test_create_rejects_bad_cron(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    res = client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "not a cron"},
    )
    assert res.status_code == 400


def test_create_404_for_missing_notebook(client: Any, lake_config: LakehouseConfig) -> None:
    res = client.post(
        "/schedules",
        json={"notebook_path": "ghost.py", "cron_expression": "* * * * *"},
    )
    assert res.status_code == 404


def test_list_schedules(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "0 * * * *"},
    )
    res = client.get("/schedules")
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_patch_toggles_enabled(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    sched = client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "0 * * * *"},
    ).json()
    res = client.patch(f"/schedules/{sched['id']}", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert res.json()["next_fire_at"] is None  # disabled → no upcoming fire


def test_patch_changes_cron(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    sched = client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "0 * * * *"},
    ).json()
    res = client.patch(f"/schedules/{sched['id']}", json={"cron_expression": "*/5 * * * *"})
    assert res.status_code == 200
    assert res.json()["cron_expression"] == "*/5 * * * *"


def test_patch_rejects_bad_cron(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    sched = client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "0 * * * *"},
    ).json()
    res = client.patch(f"/schedules/{sched['id']}", json={"cron_expression": "garbage"})
    assert res.status_code == 400


def test_delete_schedule(client: Any, lake_config: LakehouseConfig) -> None:
    _seed_notebook(lake_config)
    sched = client.post(
        "/schedules",
        json={"notebook_path": "hello.py", "cron_expression": "0 * * * *"},
    ).json()
    res = client.delete(f"/schedules/{sched['id']}")
    assert res.status_code == 204
    assert client.get("/schedules").json()["total"] == 0


def test_delete_404(client: Any) -> None:
    assert client.delete("/schedules/does-not-exist").status_code == 404
