# SPDX-License-Identifier: Apache-2.0
"""Dump the FastAPI OpenAPI schema to apps/web/openapi.json.

Used by `pnpm gen:api` in the web app to regenerate the typed client.
"""

from __future__ import annotations

import json
from pathlib import Path

from locallake_api.main import app


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "apps" / "web" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
