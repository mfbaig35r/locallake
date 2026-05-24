# SPDX-License-Identifier: Apache-2.0
"""Context template + loader tests.

The template is exec'd at runtime in a subprocess we don't own. The tests here
verify (a) it's syntactically valid Python, (b) injection produces a single
combined string, and (c) the required-packages helper deduplicates.
"""

from __future__ import annotations

import ast

from locallake_core.context import LAKE_CONTEXT_CODE, inject_context, required_packages


def test_template_is_valid_python() -> None:
    ast.parse(LAKE_CONTEXT_CODE)


def test_template_defines_lake_and_module_shim() -> None:
    assert "__lake__" in LAKE_CONTEXT_CODE
    assert "sys.modules" in LAKE_CONTEXT_CODE or "_lake_sys.modules" in LAKE_CONTEXT_CODE
    assert "_LakeContext" in LAKE_CONTEXT_CODE


def test_inject_context_prepends_template() -> None:
    user = "print('hello')"
    combined = inject_context(user)
    assert combined.endswith("print('hello')")
    assert combined.startswith(LAKE_CONTEXT_CODE[:50])
    # blank line separator guaranteed
    assert "\n\nprint('hello')" in combined


def test_required_packages_defaults() -> None:
    pkgs = required_packages()
    assert "marimo" in pkgs
    assert any(p.startswith("duckdb") for p in pkgs)


def test_required_packages_dedupes_extra() -> None:
    pkgs = required_packages(extra=["marimo", "pandas"])
    assert pkgs.count("marimo") == 1
    assert "pandas" in pkgs
