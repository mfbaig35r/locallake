# SPDX-License-Identifier: Apache-2.0
"""Demo marimo notebook — proves the `__lake__` context works end-to-end.

Run via the UI (click Run on the notebook detail page) or:
    curl -X POST http://localhost:8000/notebooks/hello.py/run
"""

import marimo

app = marimo.App()


@app.cell
def _():
    from locallake import get_connection, log, save_artifact, workspace

    return get_connection, log, save_artifact, workspace


@app.cell
def _(log):
    log("hello notebook started")
    return


@app.cell
def _(get_connection):
    con = get_connection()
    con.execute(
        "CREATE TABLE IF NOT EXISTS demo_hello (run_at TIMESTAMP DEFAULT now(), msg VARCHAR)"
    )
    con.execute("INSERT INTO demo_hello (msg) VALUES (?)", ["phase 1 demo"])
    return (con,)


@app.cell
def _(con, log):
    (count,) = con.execute("SELECT COUNT(*) FROM demo_hello").fetchone()
    log(f"demo_hello row count is now {count}")
    return (count,)


@app.cell
def _(count, save_artifact, workspace):
    save_artifact("summary.txt", f"workspace={workspace()}\nrows={count}\n")
    print(f"hello from locallake — wrote {count} rows to demo_hello")
    return


if __name__ == "__main__":
    app.run()
