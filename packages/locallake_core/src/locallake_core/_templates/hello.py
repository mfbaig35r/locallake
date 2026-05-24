# SPDX-License-Identifier: Apache-2.0
"""Demo notebook — proves the `__lake__` context works end-to-end.

Run via:
    curl -X POST http://localhost:8000/notebooks/hello.py/run

Then poll:
    curl http://localhost:8000/jobs/<job_id>
"""

from locallake import get_connection, log, save_artifact, workspace

log("hello notebook started")

con = get_connection()
con.execute("CREATE TABLE IF NOT EXISTS demo_hello (run_at TIMESTAMP DEFAULT now(), msg VARCHAR)")
con.execute("INSERT INTO demo_hello (msg) VALUES (?)", ["phase 1 demo"])

(count,) = con.execute("SELECT COUNT(*) FROM demo_hello").fetchone()
log(f"demo_hello row count is now {count}")

save_artifact("summary.txt", f"workspace={workspace()}\nrows={count}\n")

print(f"hello from locallake — wrote {count} rows to demo_hello")
