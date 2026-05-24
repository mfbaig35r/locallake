# SPDX-License-Identifier: Apache-2.0
"""Template — run a query, write the result as a parquet artifact.

Artifacts land under the per-run dir (visible on the Run detail page in the
UI). Parquet artifacts render as a previewable table.
"""

import marimo

__generated_with = "0.10.0"
app = marimo.App()


@app.cell
def _():
    from pathlib import Path

    from locallake import artifacts_dir, get_connection, log, parameters

    return Path, artifacts_dir, get_connection, log, parameters


@app.cell
def _(parameters):
    params = parameters()
    query = params.get("sql", "SELECT 1 AS hello, 'world' AS greeting")
    filename = params.get("filename", "result.parquet")
    if not filename.endswith(".parquet"):
        raise ValueError("filename must end with .parquet")
    return filename, query


@app.cell
def _(Path, artifacts_dir, filename):
    out_path = Path(artifacts_dir()) / filename
    return (out_path,)


@app.cell
def _(get_connection, log, out_path, query):
    log(f"running query: {query}")
    con = get_connection()
    con.execute(f"COPY ({query}) TO '{out_path}' (FORMAT PARQUET)")
    return (con,)


@app.cell
def _(con, filename, log, out_path):
    (row_count,) = con.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(out_path)]).fetchone()
    log(f"wrote {row_count} rows to {filename}")
    print(f"wrote {row_count} rows to artifacts/{filename}")
    return


if __name__ == "__main__":
    app.run()
