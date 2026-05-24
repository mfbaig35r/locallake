# SPDX-License-Identifier: Apache-2.0
"""Template — ingest a CSV from the workspace into a DuckDB table.

Drop a CSV at ``workspace/<your-file>.csv`` (path is relative to the workspace
root). DuckDB's ``read_csv_auto`` handles header inference + type detection.
"""

from pathlib import Path

from locallake import get_connection, log, parameters, workspace

params = parameters()
csv_relpath = params.get("csv_path", "example.csv")
table_name = params.get("table", "ingested_csv")

csv_path = Path(workspace()) / csv_relpath
if not csv_path.is_file():
    raise FileNotFoundError(
        f"CSV not found at {csv_path}. "
        "Pass parameters={'csv_path': '...'} or drop a file at workspace/example.csv"
    )

log(f"ingesting {csv_path} → {table_name}")

con = get_connection()
con.execute(
    f"""
    CREATE OR REPLACE TABLE "{table_name}" AS
    SELECT * FROM read_csv_auto(?, header=true)
    """,
    [str(csv_path)],
)
(row_count,) = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
log(f"loaded {row_count} rows into {table_name}")

print(f"loaded {row_count} rows from {csv_path.name} into {table_name}")
