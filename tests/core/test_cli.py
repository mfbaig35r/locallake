# SPDX-License-Identifier: Apache-2.0
"""`lake` CLI — init seeds templates, doctor checks paths, reset purges runs."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from locallake_core.cli import main


def test_init_scaffolds_workspace_and_seeds_templates(tmp_path: Path) -> None:
    runner = CliRunner()
    out = runner.invoke(main, ["init", "--name", "demo", "--path", str(tmp_path)])
    assert out.exit_code == 0, out.output

    assert (tmp_path / "config" / "workspace.yaml").is_file()
    assert (tmp_path / "workspace" / "notebooks").is_dir()
    assert (tmp_path / "data").is_dir()

    templates_dir = tmp_path / "workspace" / "templates"
    seeded = sorted(p.name for p in templates_dir.glob("*.py"))
    assert "hello.py" in seeded
    assert "csv_to_duckdb.py" in seeded
    assert "parquet_export.py" in seeded


def test_init_is_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    custom = tmp_path / "workspace" / "templates" / "hello.py"
    custom.write_text("# user-edited\n")

    out = runner.invoke(main, ["init", "--path", str(tmp_path)])
    assert out.exit_code == 0
    # User edits are preserved
    assert custom.read_text() == "# user-edited\n"


def test_doctor_returns_zero_for_valid_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    out = runner.invoke(main, ["doctor", "--config", str(tmp_path / "config" / "workspace.yaml")])
    assert out.exit_code == 0


def test_reset_clears_logs_and_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])

    logs = tmp_path / "workspace" / "logs"
    artifacts = tmp_path / "workspace" / "artifacts"
    (logs / "x.log").write_text("stale")
    (artifacts / "runs").mkdir()
    (artifacts / "runs" / "abc.txt").write_text("art")

    out = runner.invoke(
        main,
        [
            "reset",
            "--config",
            str(tmp_path / "config" / "workspace.yaml"),
            "--yes",
        ],
    )
    assert out.exit_code == 0, out.output
    assert list(logs.iterdir()) == []
    assert list(artifacts.iterdir()) == []


def test_start_prints_commands(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    out = runner.invoke(main, ["start", "--config", str(tmp_path / "config" / "workspace.yaml")])
    assert out.exit_code == 0
    assert "uvicorn locallake_api.main:app" in out.output
    assert "pnpm dev" in out.output
