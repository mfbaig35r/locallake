# SPDX-License-Identifier: Apache-2.0
"""Marimo editor session manager — spawns long-running `marimo edit` processes.

LocalLake opens the rich marimo editor by running ``marimo edit`` as a
subprocess and pointing the user's browser at its dev server. The lifecycle
is *not* tied to a JobRun — sessions persist until the user stops them, the
API restarts (lifespan kills them), or the host reboots.

Failure modes worth knowing about:

* If the API process dies without invoking lifespan cleanup (SIGKILL, OOM),
  spawned marimo processes survive as orphans. We track sessions in-memory
  only; on next startup, the API has no way to find them. Recovery: ``pkill
  marimo`` on the host. v2 can persist sessions to SQLite and reconcile.
* Sessions bind to ``0.0.0.0:<port>`` so Docker port-publishing works. On a
  bare host this means anyone on the local network can reach the editor.
  Acceptable for a self-hosted single-user tool; document it.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


_DEFAULT_PORT_RANGE = "2718-2727"


def _parse_port_range(spec: str) -> tuple[int, int]:
    """Parse ``2718-2727`` into ``(2718, 2727)``."""
    try:
        lo_s, hi_s = spec.split("-", 1)
        lo, hi = int(lo_s), int(hi_s)
    except ValueError as exc:
        raise ValueError(
            f"LOCALLAKE_MARIMO_PORT_RANGE must look like '2718-2727' (got {spec!r})"
        ) from exc
    if lo < 1024 or hi > 65535 or lo > hi:
        raise ValueError(f"invalid port range: {spec!r}")
    return lo, hi


@dataclass
class MarimoSession:
    notebook_path: str
    port: int
    pid: int
    started_at: datetime
    url: str
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)


class PortPoolExhaustedError(RuntimeError):
    """Every port in the configured range is held by a running session."""


class MarimoSessionManager:
    """One per API process. Thread-safe — routes run on different workers."""

    def __init__(self, port_range_spec: str | None = None) -> None:
        spec = port_range_spec or os.environ.get("LOCALLAKE_MARIMO_PORT_RANGE", _DEFAULT_PORT_RANGE)
        self._port_lo, self._port_hi = _parse_port_range(spec)
        self._sessions: dict[str, MarimoSession] = {}
        self._lock = threading.Lock()

    # ---- Public API ------------------------------------------------------

    def start(self, notebook_path: str, abs_path: Path) -> MarimoSession:
        """Spawn marimo edit for ``abs_path``; reuse an existing live session."""
        with self._lock:
            existing = self._sessions.get(notebook_path)
            if existing is not None and self._is_alive(existing):
                return existing
            if existing is not None:
                # Stale entry — process died on its own.
                self._sessions.pop(notebook_path, None)

            port = self._allocate_port_locked()
            sess = self._spawn(notebook_path, abs_path, port)
            self._sessions[notebook_path] = sess
            return sess

    def stop(self, notebook_path: str) -> bool:
        """Terminate the session for ``notebook_path``. Returns ``True`` if stopped."""
        with self._lock:
            sess = self._sessions.pop(notebook_path, None)
            if sess is None:
                return False
        self._terminate(sess)
        return True

    def get(self, notebook_path: str) -> MarimoSession | None:
        with self._lock:
            sess = self._sessions.get(notebook_path)
            if sess is None:
                return None
            if not self._is_alive(sess):
                self._sessions.pop(notebook_path, None)
                return None
            return sess

    def list_sessions(self) -> list[MarimoSession]:
        with self._lock:
            alive = [s for s in self._sessions.values() if self._is_alive(s)]
            # Drop dead entries from the map while we hold the lock.
            self._sessions = {s.notebook_path: s for s in alive}
            return list(alive)

    def stop_all(self) -> int:
        """Terminate every session — called from the API's shutdown lifespan."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for sess in sessions:
            self._terminate(sess)
        return len(sessions)

    # ---- Internals -------------------------------------------------------

    def _allocate_port_locked(self) -> int:
        used = {s.port for s in self._sessions.values() if self._is_alive(s)}
        for port in range(self._port_lo, self._port_hi + 1):
            if port not in used:
                return port
        raise PortPoolExhaustedError(f"all ports in {self._port_lo}-{self._port_hi} are in use")

    def _spawn(self, notebook_path: str, abs_path: Path, port: int) -> MarimoSession:
        cmd = [
            "marimo",
            "edit",
            f"--port={port}",
            "--no-token",
            "--headless",
            "--host=0.0.0.0",
            str(abs_path),
        ]
        logger.info("starting marimo session: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return MarimoSession(
            notebook_path=notebook_path,
            port=port,
            pid=proc.pid,
            started_at=datetime.now(UTC),
            url=f"http://localhost:{port}",
            process=proc,
        )

    @staticmethod
    def _is_alive(sess: MarimoSession) -> bool:
        proc = sess.process
        if proc is None:
            return False
        return proc.poll() is None

    @staticmethod
    def _terminate(sess: MarimoSession) -> None:
        proc = sess.process
        if proc is None or proc.poll() is not None:
            return
        try:
            # `start_new_session=True` puts the child in its own process group,
            # so we can kill it + any descendants in one go.
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=2)
        except (ProcessLookupError, PermissionError):
            # Process already gone or we don't own it — fine, we're cleaning up.
            pass
        except Exception:
            logger.exception("error terminating marimo session pid=%s", sess.pid)
