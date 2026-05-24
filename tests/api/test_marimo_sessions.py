# SPDX-License-Identifier: Apache-2.0
"""Marimo session manager — mocked subprocess so tests don't actually spawn marimo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from locallake_api.marimo_sessions import (
    MarimoSessionManager,
    MarimoSpawnError,
    PortPoolExhaustedError,
    _parse_port_range,
)


def _fake_proc(*, alive: bool = True, pid: int = 4242) -> MagicMock:
    """Return a fake Popen object that looks alive (poll() → None)."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.poll.return_value = None if alive else 0
    proc.returncode = None if alive else 0
    return proc


def _mgr(port_range_spec: str = "2718-2727") -> MarimoSessionManager:
    """Manager with the spawn grace window disabled so tests don't sleep."""
    return MarimoSessionManager(port_range_spec=port_range_spec, spawn_grace_seconds=0)


@pytest.mark.parametrize(
    "spec,expected",
    [("2718-2727", (2718, 2727)), ("9000-9001", (9000, 9001))],
)
def test_parse_port_range_valid(spec: str, expected: tuple[int, int]) -> None:
    assert _parse_port_range(spec) == expected


@pytest.mark.parametrize("spec", ["", "2718", "2727-2718", "abc-def", "1000-2000"])
def test_parse_port_range_invalid(spec: str) -> None:
    with pytest.raises(ValueError):
        _parse_port_range(spec)


def test_start_spawns_and_returns_session(tmp_path: Path) -> None:
    mgr = _mgr()
    nb = tmp_path / "hello.py"
    nb.write_text("# nb\n")
    fake = _fake_proc(pid=999)
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=fake) as popen:
        sess = mgr.start("hello.py", nb)
    popen.assert_called_once()
    cmd = popen.call_args.args[0]
    assert cmd[0] == "marimo"
    assert cmd[1] == "edit"
    assert any(a.startswith("--port=") for a in cmd)
    assert "--no-token" in cmd
    assert "--headless" in cmd
    assert sess.pid == 999
    assert sess.port == 2718
    assert sess.url == "http://localhost:2718"
    assert sess.notebook_path == "hello.py"


def test_start_reuses_live_session(tmp_path: Path) -> None:
    mgr = _mgr()
    nb = tmp_path / "hello.py"
    nb.write_text("# nb\n")
    fake = _fake_proc()
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=fake) as popen:
        first = mgr.start("hello.py", nb)
        second = mgr.start("hello.py", nb)
    assert first is second
    assert popen.call_count == 1


def test_start_replaces_dead_session(tmp_path: Path) -> None:
    """A session that dies AFTER starting gets replaced on the next start()."""
    mgr = _mgr()
    nb = tmp_path / "hello.py"
    nb.write_text("# nb\n")
    first_proc = _fake_proc(pid=1)
    second_proc = _fake_proc(pid=2)
    with patch(
        "locallake_api.marimo_sessions.subprocess.Popen",
        side_effect=[first_proc, second_proc],
    ):
        first = mgr.start("hello.py", nb)
        # Process dies later (after the grace window already passed clean).
        first_proc.poll.return_value = 0
        first_proc.returncode = 0
        second = mgr.start("hello.py", nb)
    assert second.pid == 2
    assert second is not first


def test_start_allocates_next_port_for_different_notebook(tmp_path: Path) -> None:
    mgr = _mgr("2718-2720")
    nb_a = tmp_path / "a.py"
    nb_b = tmp_path / "b.py"
    nb_a.write_text("# a")
    nb_b.write_text("# b")
    with patch(
        "locallake_api.marimo_sessions.subprocess.Popen",
        side_effect=[_fake_proc(pid=1), _fake_proc(pid=2)],
    ):
        a = mgr.start("a.py", nb_a)
        b = mgr.start("b.py", nb_b)
    assert {a.port, b.port} == {2718, 2719}


def test_start_raises_when_pool_exhausted(tmp_path: Path) -> None:
    mgr = _mgr("2718-2718")  # one slot only
    nb_a = tmp_path / "a.py"
    nb_b = tmp_path / "b.py"
    nb_a.write_text("a")
    nb_b.write_text("b")
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=_fake_proc()):
        mgr.start("a.py", nb_a)
        with pytest.raises(PortPoolExhaustedError):
            mgr.start("b.py", nb_b)


def test_start_raises_when_marimo_dies_in_grace_window(tmp_path: Path) -> None:
    """If marimo exits within the grace window, start() raises MarimoSpawnError."""
    mgr = MarimoSessionManager(
        port_range_spec="2718-2727",
        log_dir=tmp_path / "marimo-logs",
        spawn_grace_seconds=0.05,
    )
    nb = tmp_path / "broken.py"
    nb.write_text("# nb\n")
    dying = _fake_proc()
    dying.poll.return_value = 42  # already exited by the time we check
    dying.returncode = 42
    with (
        patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=dying),
        pytest.raises(MarimoSpawnError) as excinfo,
    ):
        mgr.start("broken.py", nb)
    # The error message includes the exit code, and the session is gone from
    # the manager so the next start retries cleanly.
    assert "exit=42" in str(excinfo.value)
    assert mgr.get("broken.py") is None


def test_get_returns_none_when_process_died(tmp_path: Path) -> None:
    mgr = _mgr()
    nb = tmp_path / "x.py"
    nb.write_text("x")
    fake = _fake_proc()
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=fake):
        mgr.start("x.py", nb)
    fake.poll.return_value = 0  # process died
    assert mgr.get("x.py") is None


def test_stop_terminates_and_removes(tmp_path: Path) -> None:
    mgr = _mgr()
    nb = tmp_path / "x.py"
    nb.write_text("x")
    fake = _fake_proc()
    with (
        patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=fake),
        patch("locallake_api.marimo_sessions.os.killpg") as killpg,
        patch("locallake_api.marimo_sessions.os.getpgid", return_value=fake.pid),
    ):
        mgr.start("x.py", nb)
        assert mgr.stop("x.py") is True
    killpg.assert_called()
    assert mgr.get("x.py") is None


def test_stop_returns_false_for_unknown(tmp_path: Path) -> None:
    mgr = _mgr()
    assert mgr.stop("nothing-here.py") is False


def test_stop_all_terminates_every_session(tmp_path: Path) -> None:
    mgr = _mgr()
    for i, name in enumerate(["a.py", "b.py", "c.py"]):
        nb = tmp_path / name
        nb.write_text("x")
        with patch(
            "locallake_api.marimo_sessions.subprocess.Popen",
            return_value=_fake_proc(pid=i + 1),
        ):
            mgr.start(name, nb)
    with (
        patch("locallake_api.marimo_sessions.os.killpg") as killpg,
        patch("locallake_api.marimo_sessions.os.getpgid", side_effect=lambda p: p),
    ):
        count = mgr.stop_all()
    assert count == 3
    assert killpg.call_count == 3
    assert mgr.list_sessions() == []


def _client_with_marimo(client: Any, manager: MarimoSessionManager) -> Any:
    """Override the marimo session manager dep so each test gets a fresh one."""
    from locallake_api.deps import get_marimo_sessions
    from locallake_api.main import app

    app.dependency_overrides[get_marimo_sessions] = lambda: manager
    return client


def test_route_open_starts_session(client: Any, lake_config: Any) -> None:
    """POST /notebooks/{path}/edit returns the session URL."""
    nb = Path(lake_config.paths.notebooks) / "hi.py"
    nb.write_text("# nb\n")
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=_fake_proc(pid=7)):
        res = client.post("/notebooks/hi.py/edit")
    assert res.status_code == 201
    body = res.json()
    assert body["url"].startswith("http://localhost:")
    assert body["pid"] == 7


def test_route_open_404_for_missing(client: Any) -> None:
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    res = client.post("/notebooks/ghost.py/edit")
    assert res.status_code == 404


def test_route_get_returns_running_session(client: Any, lake_config: Any) -> None:
    nb = Path(lake_config.paths.notebooks) / "hi.py"
    nb.write_text("# nb\n")
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    with patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=_fake_proc(pid=11)):
        client.post("/notebooks/hi.py/edit")
    res = client.get("/notebooks/hi.py/edit")
    assert res.status_code == 200
    assert res.json()["pid"] == 11


def test_route_get_returns_null_when_none(client: Any, lake_config: Any) -> None:
    nb = Path(lake_config.paths.notebooks) / "hi.py"
    nb.write_text("# nb\n")
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    res = client.get("/notebooks/hi.py/edit")
    assert res.status_code == 200
    assert res.json() is None


def test_route_delete_stops_session(client: Any, lake_config: Any) -> None:
    nb = Path(lake_config.paths.notebooks) / "hi.py"
    nb.write_text("# nb\n")
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    with (
        patch("locallake_api.marimo_sessions.subprocess.Popen", return_value=_fake_proc()),
        patch("locallake_api.marimo_sessions.os.killpg"),
        patch("locallake_api.marimo_sessions.os.getpgid", side_effect=lambda p: p),
    ):
        client.post("/notebooks/hi.py/edit")
        res = client.delete("/notebooks/hi.py/edit")
    assert res.status_code == 204


def test_route_delete_404_for_no_session(client: Any) -> None:
    mgr = _mgr()
    _client_with_marimo(client, mgr)
    res = client.delete("/notebooks/nothing.py/edit")
    assert res.status_code == 404
