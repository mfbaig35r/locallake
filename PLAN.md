# LocalLake — Build Plan

> **Status:** v1.0 shipped (2026-05-24) · **Owner:** Fahad Baig · **Drafted:** 2026-05-23
> **License:** Apache-2.0
> **Repo:** `~/Projects/locallake/`

A local-first, open-source analytics workspace built with marimo, DuckDB, FastAPI, and Next.js. Databricks-style workflow (notebooks, SQL, jobs, artifacts, git-native) on your own machine, no cloud bill.

---

## 1. Naming & conventions

| Thing | Value |
|---|---|
| Product name | **LocalLake** |
| Repo | `~/Projects/locallake/` (github.com/mfbaig35r/locallake) |
| User-facing pip pkg | `locallake` (the notebook helper) |
| Internal packages | `locallake_core`, `locallake_api`, `locallake_worker` |
| CLI binary | `lake` |
| Notebook context object | `__lake__` (injected, also re-exported by `locallake`) |
| Env var prefix | `LOCALLAKE_*` |
| Config file | `config/workspace.yaml` |
| Metadata DB | `data/metadata.sqlite` |
| User data DB | `data/local.duckdb` (configurable) |

---

## 2. Load-bearing architecture decisions

These are the calls that, if wrong, force rework. Locked in for v1.

| Decision | Choice | Why |
|---|---|---|
| **Notebook runtime** | Wrap `marimo-sandbox`, add our own job model on top | marimo-sandbox already does subprocess exec, env caching, dry-run, approvals, artifacts. Our layer adds workspace scoping, scheduling, DAGs, run↔git mapping |
| **Queue** | `arq` | Async-native, fits FastAPI, ~10× less ceremony than Celery, same Redis backend |
| **Metadata store** | SQLite (WAL mode) as source of truth | One writer (API), many readers (worker, UI). marimo-sandbox's JSON runs are *linked* via `mcp_run_id`, not synced |
| **Migrations** | Alembic + SQLAlchemy 2 (sync) from day 1 | You will add columns. Don't paint into a corner |
| **DuckDB concurrency** | Short-lived connections + exponential-backoff retry (5 attempts, 50ms base) | Three processes (FastAPI, worker, notebook subprocess) all touch one `.duckdb` file. Port pattern verbatim from AGI's `duckdb_backend.py:49-67` + `context_template.py:32-48` |
| **Notebook context** | AGI-style injected `__lake__` + thin `locallake` pip package shim | Notebook venv stays clean (only `locallake` installed); users still get the `from locallake import get_connection` ergonomic |
| **Distribution** | Docker Compose for users, `uv run` + `pnpm dev` for dev | Compose is the install story. Dev iteration in Docker is too slow |
| **Auth** | Single-user, optional `LOCALLAKE_PASSWORD` env. Signed-cookie sessions. No RBAC | Matches self-hosted single-user norms (Gitea, Linkding) |
| **Container paths** | `workspace.yaml` uses container paths; host paths via compose volumes | Documented in README — single biggest gotcha for users |
| **Web framework** | Next.js 16 App Router + shadcn/ui | Reuses the design-system muscle from sourcing-kernel-ui / tekni-mcp-ui |
| **License** | Apache-2.0 | Open-source-first positioning |

---

## 3. Repo structure

```
locallake/
├── apps/
│   ├── api/                            # FastAPI control plane
│   │   ├── pyproject.toml
│   │   └── src/locallake_api/
│   │       ├── main.py                 # FastAPI app factory
│   │       ├── routes/                 # /jobs, /sql, /notebooks, /git, /catalog
│   │       ├── websocket.py            # MODULE-LEVEL routes only
│   │       ├── auth.py
│   │       ├── db.py                   # SQLite session
│   │       └── deps.py
│   ├── worker/                         # arq worker
│   │   ├── pyproject.toml
│   │   └── src/locallake_worker/
│   │       ├── main.py                 # arq WorkerSettings
│   │       ├── jobs.py                 # run_notebook task
│   │       ├── schedules.py            # cron-driven jobs
│   │       └── runner.py               # wraps marimo_sandbox._impl_run_python
│   └── web/                            # Next.js 16
│       ├── package.json
│       └── app/...
├── packages/
│   ├── locallake/                      # pip-installable notebook helper (~30 LOC)
│   │   ├── pyproject.toml
│   │   └── src/locallake/__init__.py   # re-exports from __lake__
│   └── locallake_core/                 # shared between api + worker
│       ├── pyproject.toml
│       └── src/locallake_core/
│           ├── config.py               # workspace.yaml loader (pydantic)
│           ├── models.py               # SQLAlchemy models
│           ├── alembic/                # migrations
│           ├── duckdb_conn.py          # short-lived + retry (port from AGI)
│           ├── context_template.py     # __lake__ injection (port from AGI)
│           └── git.py                  # subprocess wrappers
├── workspace/                          # user-facing, mounted as volume
│   ├── notebooks/
│   ├── artifacts/
│   ├── logs/
│   └── templates/                      # notebook starter templates
├── data/                               # mounted as volume
│   ├── metadata.sqlite                 # app metadata (LocalLake-owned)
│   └── local.duckdb                    # user data
├── config/
│   └── workspace.yaml
├── docker-compose.yml
├── docker-compose.dev.yml              # overrides for dev (mount source)
├── Dockerfile.api
├── Dockerfile.worker
├── Dockerfile.web
├── PLAN.md                             # this file
├── README.md
└── LICENSE                             # Apache-2.0
```

**`locallake_core` is the most important structural call** — both api and worker depend on it, preventing drift between the two processes' view of config, models, and connection patterns.

---

## 4. SQLite data model (v1)

```python
# packages/locallake_core/src/locallake_core/models.py

class JobRun(Base):
    id: Mapped[str] = mapped_column(primary_key=True)         # uuid4
    notebook_path: Mapped[str]                                 # relative to workspace
    status: Mapped[str]                                        # queued|running|success|failed|cancelled
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration_seconds: Mapped[float | None]
    triggered_by: Mapped[str]                                  # user|schedule|api|webhook
    git_commit_sha: Mapped[str | None]                         # captured at submission
    git_dirty: Mapped[bool]                                    # captured at submission
    error_message: Mapped[str | None]
    log_path: Mapped[str | None]                               # workspace-relative
    artifact_path: Mapped[str | None]
    mcp_run_id: Mapped[str | None]                             # marimo-sandbox run_id
    parameters_json: Mapped[str]                               # JSON
    parent_run_id: Mapped[str | None]                          # FK for DAG/lineage
    schedule_id: Mapped[str | None]                            # FK
    timeout_seconds: Mapped[int]

class Schedule(Base):                                          # table in v1, page in v2
    id: Mapped[str] = mapped_column(primary_key=True)
    notebook_path: Mapped[str]
    cron_expression: Mapped[str]                               # "0 6 * * *"
    enabled: Mapped[bool]
    last_run_at: Mapped[datetime | None]
    last_run_id: Mapped[str | None]
    created_at: Mapped[datetime]
    parameters_json: Mapped[str]

class SavedQuery(Base):
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    sql: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

class QueryHistory(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    sql: Mapped[str]
    executed_at: Mapped[datetime]
    duration_ms: Mapped[int]
    row_count: Mapped[int | None]
    error_message: Mapped[str | None]
```

**Reserved names for future migrations** (don't claim now, but don't shadow): `dag_definitions`, `dag_steps`, `users`, `api_keys`, `webhooks`.

Notebooks are *not* a table — filesystem-scanned on `GET /notebooks`. Caching is premature.

---

## 5. Notebook context: dual API

```python
# packages/locallake/src/locallake/__init__.py — the entire pip package
"""Thin shim. Actual implementation is injected at runtime as __lake__."""
import builtins

def get_connection():
    """Return a DuckDB connection to the configured workspace database."""
    return builtins.__lake__.connection()

def workspace():
    """Return the workspace root path."""
    return builtins.__lake__.workspace()

def artifacts_dir():
    """Return this run's artifacts directory."""
    return builtins.__lake__.artifacts_dir()

def save_artifact(name: str, data: bytes | str) -> str:
    """Persist an artifact for this run; returns the path."""
    return builtins.__lake__.save_artifact(name, data)

def log(msg: str, level: str = "info") -> None:
    """Structured log line to this run's log file."""
    return builtins.__lake__.log(msg, level)

def parameters() -> dict:
    """Return the parameters passed to this run."""
    return builtins.__lake__.parameters()
```

The notebook venv installs only `locallake` (tiny). `locallake_core` and `locallake_api` are never installed into the subprocess — same isolation pattern AGI uses with `context_template.py`.

---

## 6. API surface (v1 complete)

```
# Health & config
GET    /health
GET    /workspace                       # read workspace.yaml
PUT    /workspace                       # write workspace.yaml (validates)

# Notebooks (filesystem-backed)
GET    /notebooks                       # tree of workspace/notebooks
GET    /notebooks/{path}                # metadata + last 10 runs
POST   /notebooks/{path}/run            # enqueue, returns job_id
GET    /templates                       # list templates
POST   /notebooks                       # create new from template

# Jobs
GET    /jobs                            # paginated, filter by status/notebook/since
GET    /jobs/{id}
POST   /jobs/{id}/cancel
GET    /jobs/{id}/artifacts             # list
GET    /jobs/{id}/artifacts/{path}      # download
WS     /jobs/{id}/logs                  # tail stdout/stderr live (MODULE-LEVEL ROUTE)

# SQL & catalog
POST   /sql/query                       # read-only, timeout, row limit
GET    /sql/saved
POST   /sql/saved
DELETE /sql/saved/{id}
GET    /sql/history
GET    /catalog/tables                  # introspect DuckDB
GET    /catalog/tables/{schema}/{name}

# Git
GET    /git/status                      # branch, dirty, ahead/behind
GET    /git/log                         # last N commits

# Schedules (table in v1, full UI in v2)
GET    /schedules
POST   /schedules
PATCH  /schedules/{id}                  # enable/disable, edit cron
DELETE /schedules/{id}
```

---

## 7. Frontend pages (v1 complete)

| Route | Purpose |
|---|---|
| `/` | Dashboard: workspace name, db path, last 5 runs, last 5 notebooks, git status, system health |
| `/notebooks` | Tree browser, run button per row, quick stats column |
| `/notebooks/[...path]` | Notebook detail: metadata, recent runs, parameters form, "Run" + "Open in marimo" |
| `/jobs` | Runs list: filter by status/notebook/date, paginated, status pills |
| `/jobs/[id]` | Run detail: status, duration, params, **live log stream**, artifacts list, error stack |
| `/sql` | Monaco editor, results grid, schema sidebar, saved queries dropdown, history drawer |
| `/catalog` | Schema browser: tables, columns, row counts, sample preview |
| `/schedules` | Schedules table, create-from-notebook modal (v2) |
| `/settings` | Edit workspace.yaml fields with validation |

**UI stack:** Next.js 16 App Router, shadcn/ui, TanStack Query for data, Monaco for SQL editor, recharts for viz, lucide icons. Typed API client generated from FastAPI's `/openapi.json` via `openapi-typescript`.

---

## 8. Docker Compose

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    volumes: ["redis-data:/data"]

  api:
    build: {context: ., dockerfile: Dockerfile.api}
    ports: ["8000:8000"]
    environment:
      LOCALLAKE_CONFIG: /config/workspace.yaml
      LOCALLAKE_METADATA_DB: /data/metadata.sqlite
      REDIS_URL: redis://redis:6379
      LOCALLAKE_PASSWORD: ${LOCALLAKE_PASSWORD:-}
    volumes:
      - ./workspace:/workspace
      - ./data:/data
      - ./config:/config
    depends_on: [redis]

  worker:
    build: {context: ., dockerfile: Dockerfile.worker}
    environment:
      LOCALLAKE_CONFIG: /config/workspace.yaml
      LOCALLAKE_METADATA_DB: /data/metadata.sqlite
      REDIS_URL: redis://redis:6379
    volumes:
      - ./workspace:/workspace
      - ./data:/data
      - ./config:/config
      - marimo-cache:/root/.marimo-sandbox       # cache venvs across restarts
    depends_on: [redis]

  web:
    build: {context: ., dockerfile: Dockerfile.web}
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on: [api]

volumes:
  redis-data:
  marimo-cache:
```

User flow: `git clone && docker compose up && open http://localhost:3000`.

---

## 9. Phased build plan

**Total: ~4-5 weeks focused for v1.0.** Each phase ends with something demonstrable.

### Phase 0 — Foundations (2-3 days)
- Monorepo init, `pyproject.toml`s with `uv` workspaces, `package.json` for web
- `locallake_core` package: config loader, SQLAlchemy models, Alembic init + first migration
- `workspace.yaml` schema (pydantic)
- Docker Compose skeleton (services boot, nothing useful yet)
- CI: ruff check + format, mypy, pytest skeleton
- **Demo:** `docker compose up` brings up empty services; `lake init` CLI scaffolds a workspace

### Phase 1 — Job runtime (4-5 days)
- Port `context_template.py` from AGI, adapt for LocalLake (`__lake__` namespace)
- Port DuckDB short-lived-connection + retry pattern
- `locallake` pip package (the 30-LOC shim)
- `JobRunner` in `locallake_core` wrapping `marimo_sandbox._impl_run_python`
- arq worker process; `run_notebook` task
- API: `POST /notebooks/{path}/run`, `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`
- Capture git SHA + dirty status at submission
- **Demo:** `curl POST /notebooks/hello.py/run` → poll `/jobs/{id}` → see success + artifacts on disk

### Phase 2 — UI shell (5-6 days)
- Next.js scaffold, shadcn install, dark theme baseline
- Auth middleware: checks signed cookie if `LOCALLAKE_PASSWORD` set
- Layout: sidebar (Dashboard/Notebooks/Jobs/SQL/Catalog/Schedules/Settings), top bar with git branch
- TanStack Query setup, typed API client via `openapi-typescript`
- Pages: dashboard, notebooks browser, runs list, run detail (no live logs yet)
- **Demo:** click "Run" on a notebook in UI → see it appear in runs list → see status update → click into run detail

### Phase 3 — Logs + artifacts (3-4 days)
- WebSocket `/jobs/{id}/logs` (**module-level route**)
- Tail stdout/stderr from `~/.marimo-sandbox/runs/{mcp_run_id}/` as written
- Frontend: xterm.js or simple line list with autoscroll
- Artifact listing API + download endpoint
- Frontend: artifacts grid with file-type icons, click-to-download
- Render parquet artifacts as a table preview (use `duckdb` to peek)
- **Demo:** run a 30s notebook → watch logs stream in real time → see parquet artifact previewable

### Phase 4 — SQL + catalog (3-4 days)
- Read-only DuckDB connection helper (`read_only=True` + retry)
- `POST /sql/query` with timeout + row limit + memory limit
- Reject destructive SQL via dialect pattern (copy AGI's `DuckDBDialect` refusal list)
- Saved queries + history CRUD
- Frontend: Monaco editor with SQL mode, results grid (TanStack Table), schema sidebar
- Catalog page: tables list, click into table → columns + sample
- **Demo:** run a SELECT in UI, save it, see it in history; browse schema, click table to preview

### Phase 5 — Templates + Git + polish (3-4 days)
- `workspace/templates/` directory: `hello.py`, `csv_to_duckdb.py`, `parquet_export.py`, each demonstrating `__lake__` / `locallake` usage
- `POST /notebooks` creates from template
- `GET /git/status`, `GET /git/log` — subprocess calls
- Git status pill in top bar
- `lake init`, `lake start`, `lake reset`, `lake doctor` CLI
- README + screenshots + "why this exists"
- Landing copy in dashboard for empty-state
- **Ship v1.0**

### Phase 6 — Schedules (3-4 days, post-v1)
- arq cron support wired to `Schedule` table
- Worker pulls active rows on startup, registers cron functions
- API + UI for create/edit/disable schedules
- "Create schedule from this notebook" button in notebook detail

### Phase 7 — Hardening (ongoing)
- Run retry policy (per-notebook config)
- Pagination/filtering on all list endpoints
- SQLite + DuckDB backup CLI (`lake backup`)
- Worker concurrency (multiple arq workers; priority queues later)
- Notebook output rendering: matplotlib PNGs, plotly HTML, markdown cells

---

## 10. Risk register

| # | Risk | Mitigation |
|---|---|---|
| 1 | DuckDB file lock contention (FastAPI + worker + notebook subprocess all hit one file) | Retry pattern from AGI; `read_only=True` on API side; escape hatch documented for v2+ (Postgres for metadata, MotherDuck for shared user data) |
| 2 | FastAPI WebSocket routes 403 on handshake | Module-level routes only. Codified in `apps/api/src/locallake_api/websocket.py` with a comment pointing at the gotcha |
| 3 | Container vs host path confusion | README has a big "Paths" section. `workspace.yaml` validation rejects host-style paths. `lake doctor` checks paths exist |
| 4 | Notebook path traversal in `POST /notebooks/{path}/run` | pydantic validator: must be relative, no `..`, must resolve under workspace dir |
| 5 | SQL injection / destructive ops on `/sql/query` | Read-only DuckDB connection; reject patterns from AGI's `DuckDBDialect.DESTRUCTIVE_PATTERNS`; query timeout (30s default); row limit (10k default) |
| 6 | marimo-sandbox env inheritance leaks secrets to notebook subprocess | Document the same caveat AGI documents (`context_template.py:51-61`). Provide a `locallake secrets` namespace later that filters env vars |
| 7 | Long notebook blocks the only worker | Worker count via `LOCALLAKE_WORKER_CONCURRENCY`, default 2. Documented |
| 8 | SQLite WAL on Docker volume can corrupt on host crash | `synchronous=NORMAL` + nightly backup CLI. Acceptable for local-first single-user |
| 9 | marimo-sandbox version drift | Pin in `apps/worker/pyproject.toml`. Test matrix in CI |
| 10 | Git shelling out unsafely | `subprocess.run(shell=False, ...)`, fixed argv, timeout. No user input passed to git |
| 11 | arq job that crashes silently | Wrap `run_notebook` in try/except, always update `JobRun.status` + `error_message` before re-raising |
| 12 | First-time install pulls marimo + duckdb + every dep | Layer Dockerfile.worker carefully; cache `~/.marimo-sandbox` volume so re-runs are fast |

---

## 11. Deliberately deferred (v2+)

These are tagged because they will get asked for. The data model + interfaces should not foreclose them.

- **MLflow integration** — wait for someone to ask
- **DAG editor** — `parent_run_id` column reserves the lineage shape; build UI when needed
- **MotherDuck / S3 sync** — out of scope; users can write notebooks that sync
- **AI assistant / MCP server** — natural Phase 8 once the surface stabilizes
- **Multi-user / RBAC** — explicit non-goal; don't let it creep in
- **Real-time collaborative notebook editing** — same
- **Remote workers** — single-machine for now; queue is Redis so this is technically possible later
- **Webhook triggers for jobs** — easy add to arq once the basic flow ships

---

## 12. Open implementation questions

To resolve as we get into each phase, not now:

1. **Notebook output rendering** — for matplotlib/plotly, do we capture via marimo's native output system, or scrape stdout for `__output__` markers? (Phase 3)
2. **Parameters UI** — free-form JSON editor, or parse marimo `mo.ui.*` widgets and render typed inputs? (Phase 2-3 decision)
3. **Saved queries — file-backed or DB-backed?** Going DB-backed for v1 (SQLite), but consider exporting to `workspace/queries/*.sql` so git-versionable
4. **Run retention policy** — auto-purge runs older than N days? Configurable, default off, surface as `lake purge` CLI
5. **First-run experience** — when `workspace/notebooks/` is empty, do we ship one demo notebook? Yes — phase 5 creates `hello.py` from a template
