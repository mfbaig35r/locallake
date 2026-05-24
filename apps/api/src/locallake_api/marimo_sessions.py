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
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


_DEFAULT_PORT_RANGE = "2718-2727"


def _tail_log(path: str | None, *, lines: int) -> str:
    """Best-effort read of the last N lines of ``path``. Empty string on failure."""
    if not path:
        return ""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except OSError:
        return ""


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
    log_path: str | None = None
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)


class PortPoolExhaustedError(RuntimeError):
    """Every port in the configured range is held by a running session."""


class MarimoSpawnError(RuntimeError):
    """marimo died within the post-spawn grace window. See ``log_path``."""

    def __init__(self, message: str, log_path: str | None) -> None:
        super().__init__(message)
        self.log_path = log_path


class MarimoSessionManager:
    """One per API process. Thread-safe — routes run on different workers."""

    def __init__(
        self,
        port_range_spec: str | None = None,
        *,
        log_dir: Path | None = None,
        spawn_grace_seconds: float = 0.5,
    ) -> None:
        spec = port_range_spec or os.environ.get("LOCALLAKE_MARIMO_PORT_RANGE", _DEFAULT_PORT_RANGE)
        self._port_lo, self._port_hi = _parse_port_range(spec)
        self._sessions: dict[str, MarimoSession] = {}
        self._lock = threading.Lock()
        # Where to tee marimo's stdout/stderr. Default is /tmp because the
        # workspace logs dir may not exist at manager construction time.
        env_dir = os.environ.get("LOCALLAKE_MARIMO_LOG_DIR")
        self._log_dir = log_dir or (Path(env_dir) if env_dir else Path("/tmp/locallake-marimo"))
        # Post-spawn liveness window. Long enough to catch marimo dying on a
        # bad flag or port-bind failure, short enough not to block the route.
        # Tests set this to 0 to skip the sleep entirely.
        self._spawn_grace_seconds = spawn_grace_seconds

    # ---- Public API ------------------------------------------------------

    def start(self, notebook_path: str, abs_path: Path) -> MarimoSession:
        """Spawn marimo edit for ``abs_path``; reuse an existing live session.

        Includes a short post-spawn grace check — marimo sometimes exits within
        the first second on bad flags or port-bind failures, and we'd rather
        surface that here than via a useless "session started" + browser
        ERR_CONNECTION_RESET later.
        """
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

        # Outside the lock — sleep is short but we shouldn't pin the manager.
        if self._spawn_grace_seconds > 0:
            time.sleep(self._spawn_grace_seconds)
        if sess.process is not None and sess.process.poll() is not None:
            with self._lock:
                self._sessions.pop(notebook_path, None)
            tail = _tail_log(sess.log_path, lines=20)
            # marimo's most common refusal: file isn't a marimo notebook.
            # Surface that with a short, actionable message instead of the
            # 20-line dump so the UI can show something readable.
            if "not recognized as a marimo notebook" in tail:
                raise MarimoSpawnError(
                    f"{notebook_path} isn't a marimo notebook. Convert it inside "
                    "the API container: "
                    f"`docker compose exec api marimo convert {abs_path}`, then "
                    "save the result over the original.",
                    sess.log_path,
                )
            raise MarimoSpawnError(
                f"marimo exited immediately (exit={sess.process.returncode}). "
                f"Last 20 log lines:\n{tail}",
                sess.log_path,
            )
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
            "--skip-update-check",
            str(abs_path),
        ]
        # Per-session log so the user can debug "why didn't marimo start" by
        # tailing one file. Stays around until manager.stop() (intentional —
        # post-mortem after a crash is more valuable than tidy).
        self._log_dir.mkdir(parents=True, exist_ok=True)
        safe_name = notebook_path.replace("/", "__")
        log_path = self._log_dir / f"marimo-{safe_name}-{port}.log"
        # Popen owns this handle for the lifetime of the subprocess — a
        # `with` block would close it the moment we exit the function and
        # marimo would lose its stdout sink.
        log_fh = open(log_path, "wb")  # noqa: SIM115
        logger.info("starting marimo session: %s (log=%s)", " ".join(cmd), log_path)
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return MarimoSession(
            notebook_path=notebook_path,
            port=port,
            pid=proc.pid,
            started_at=datetime.now(UTC),
            url=f"http://localhost:{port}",
            log_path=str(log_path),
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
