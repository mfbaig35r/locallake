# SPDX-License-Identifier: Apache-2.0
"""Template — run a query, write the result as a parquet artifact.

Artifacts land under the per-run dir (visible on the Run detail page in the
UI). Parquet artifacts render as a previewable table.
"""

from pathlib import Path

from locallake import artifacts_dir, get_connection, log, parameters

params = parameters()
query = params.get("sql", "SELECT 1 AS hello, 'world' AS greeting")
filename = params.get("filename", "result.parquet")

if not filename.endswith(".parquet"):
    raise ValueError("filename must end with .parquet")

log(f"running query: {query}")

con = get_connection()
out_path = Path(artifacts_dir()) / filename
con.execute(
    f"COPY ({query}) TO '{out_path}' (FORMAT PARQUET)"
)
(row_count,) = con.execute(
    "SELECT COUNT(*) FROM read_parquet(?)", [str(out_path)]
).fetchone()

log(f"wrote {row_count} rows to {filename}")
print(f"wrote {row_count} rows to artifacts/{filename}")
