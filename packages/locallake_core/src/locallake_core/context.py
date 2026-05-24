# SPDX-License-Identifier: Apache-2.0
"""Loader for the ``__lake__`` context template.

The template is a real Python file (so it gets IDE support + linting) but at
runtime it's just a string prepended to the notebook code before submission
to marimo-sandbox.
"""

from __future__ import annotations

from pathlib import Path

LAKE_CONTEXT_CODE: str = Path(__file__).with_name("context_template.py").read_text(encoding="utf-8")

_BASE_PACKAGES: list[str] = ["marimo", "duckdb>=1.0.0"]


def required_packages(extra: list[str] | None = None) -> list[str]:
    """Return the package list to install in the notebook venv.

    Deduplicates while preserving order so test assertions are stable.
    """
    pkgs = list(_BASE_PACKAGES)
    for p in extra or []:
        if p not in pkgs:
            pkgs.append(p)
    return pkgs


def inject_context(user_code: str) -> str:
    """Prepend the ``__lake__`` template to user notebook code.

    Forces a blank-line separator so the first line of user code is never
    concatenated onto the last line of the template.
    """
    return LAKE_CONTEXT_CODE.rstrip() + "\n\n" + user_code
