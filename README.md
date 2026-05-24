# LocalLake

> A local-first, open-source analytics workspace built with marimo, DuckDB, FastAPI, and Next.js. Databricks-style workflow on your own machine — no cloud bill.

**Status:** v1.0. See [PLAN.md](./PLAN.md) for the design notes behind each phase.

## Why

Most analytics tooling forces a choice: cloud-hosted bills + lock-in, or rolling your own marimo + Jupyter + duckdb + cron setup. LocalLake bundles the second option into a single workspace you can `docker compose up`. One DuckDB file, one metadata SQLite, one notebook runtime, and a UI that handles the "I just want to see logs and re-run that thing" loop. Everything stays on your disk.

## What's in v1.0

- **Notebooks** — marimo `.py` files in `workspace/notebooks/`, run via the UI or `POST /notebooks/{path}/run`. Each run captures git SHA + dirty status at submission.
- **Templates** — starter notebooks (`hello.py`, `csv_to_duckdb.py`, `parquet_export.py`) seeded by `lake init`. Create new notebooks from a template in the UI.
- **Logs + artifacts** — every run writes to `workspace/logs/<job_id>.log`. The UI tails it over a WebSocket while the run is in flight. Parquet artifacts preview inline.
- **SQL** — Monaco editor over a read-only DuckDB connection. Saved queries + history in SQLite. Allowlist (SELECT / WITH / SHOW / DESCRIBE / EXPLAIN), single-statement enforcement, configurable timeout via `conn.interrupt()`.
- **Catalog** — schema browser: tables and views with column metadata, row count, and a 50-row sample.
- **Git** — branch + dirty + ahead/behind in the topbar; recent commits via `/git/log`.
- **Single-user auth** — optional `LOCALLAKE_PASSWORD` env. Signed-cookie sessions, no RBAC.

## Quick start (dev)

```bash
uv sync --all-packages
uv run lake init --path .

# Three terminals:
uv run --package locallake-api uvicorn locallake_api.main:app --reload --port 8000
uv run --package locallake-worker arq locallake_worker.main.WorkerSettings
cd apps/web && pnpm install && pnpm dev
```

Open <http://localhost:3000>.

## Quick start (Docker)

```bash
uv run lake init --path .
docker compose up
```

Open <http://localhost:3000>.

## CLI

```
lake init      # scaffold a workspace + seed templates
lake start     # print the dev start commands
lake doctor    # diagnose common setup issues
lake reset     # clear logs + artifacts (keeps notebooks + DB)
```

## Architecture

```
                ┌──────────────────┐
                │   Next.js (3000) │     /sql, /catalog, /jobs/[id], …
                └────────┬─────────┘
                         │ openapi-fetch
                ┌────────▼─────────┐
                │  FastAPI (8000)  │     /sql/query, /catalog/*, /jobs/*,
                │                  │     ws /jobs/{id}/logs, /git/*, …
                └───┬──────┬───────┘
                    │      │ arq (Redis)
        ┌───────────▼─┐  ┌─▼──────────────┐
        │  SQLite     │  │  arq worker    │
        │  metadata   │  │  → marimo-     │
        │  (jobs,     │  │     sandbox    │
        │   saved,    │  │     subprocess │
        │   history)  │  │                │
        └─────────────┘  └─┬──────────────┘
                           │ inherits __lake__ context
                  ┌────────▼─────────┐
                  │  notebook venv   │     get_connection() → DuckDB
                  │  (marimo + duckdb│     workspace() / artifacts_dir()
                  │   + locallake    │     save_artifact() / log()
                  │   shim)          │
                  └──────────────────┘
```

DuckDB is touched by three processes — API (SQL page, read-only), worker (held during a notebook run), notebook subprocess (read/write). Cross-process file lock contention is handled by short-lived connections with exponential-backoff retry in `locallake_core/duckdb_conn.py`.

See [PLAN.md §2](./PLAN.md#2-load-bearing-architecture-decisions) for the design decisions that, if wrong, would force a rewrite.

## Repo layout

```
apps/{api,worker,web}        # FastAPI control plane, arq worker, Next.js UI
packages/locallake           # tiny notebook helper (the pip-installable shim)
packages/locallake_core      # shared: config, models, migrations, CLI, templates
workspace/                   # user-mounted: notebooks, artifacts, logs, templates
data/                        # user-mounted: metadata.sqlite + local.duckdb
config/workspace.yaml        # workspace configuration
```

## Deliberately not in v1.0

DAG editor, MLflow integration, MotherDuck/S3 sync, multi-user / RBAC, remote workers, real-time collaborative editing. The data model + interfaces don't foreclose these — see [PLAN.md §11](./PLAN.md#11-deliberately-deferred-v2).

## License

Apache-2.0. See [LICENSE](./LICENSE).
