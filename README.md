# LocalLake

> A local-first, open-source analytics workspace built with marimo, DuckDB, FastAPI, and Next.js. Databricks-style workflow on your own machine — no cloud bill.

**Status:** Phase 0 (foundations). See [PLAN.md](./PLAN.md) for the full build plan.

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

## Repo layout

```
apps/{api,worker,web}        # FastAPI control plane, arq worker, Next.js UI
packages/locallake           # tiny notebook helper (the pip-installable shim)
packages/locallake_core      # shared: config, models, migrations, CLI
workspace/                   # user-mounted: notebooks, artifacts, logs, templates
data/                        # user-mounted: metadata.sqlite + local.duckdb
config/workspace.yaml        # workspace configuration
```

## Architecture

See [PLAN.md §2](./PLAN.md#2-load-bearing-architecture-decisions) for the load-bearing design decisions.

## License

Apache-2.0. See [LICENSE](./LICENSE).
