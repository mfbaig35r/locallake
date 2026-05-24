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


def test_backup_bundles_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    # Seed a notebook + a fake artifact + a fake log file
    (tmp_path / "workspace" / "notebooks" / "my.py").write_text("# my notebook\n")
    (tmp_path / "workspace" / "artifacts" / "stale.txt").write_text("artifact body")
    (tmp_path / "workspace" / "logs" / "old.log").write_text("log body")
    (tmp_path / "data" / "local.duckdb").write_bytes(b"\x00" * 16)

    out = runner.invoke(
        main,
        [
            "backup",
            "--config",
            str(tmp_path / "config" / "workspace.yaml"),
            "--to",
            str(tmp_path / "backups"),
        ],
    )
    assert out.exit_code == 0, out.output

    archives = list((tmp_path / "backups").glob("*.tar.gz"))
    assert len(archives) == 1

    import tarfile

    with tarfile.open(archives[0], "r:gz") as tar:
        names = tar.getnames()
    assert any(n.endswith("notebooks/my.py") for n in names)
    assert any(n.endswith("config/workspace.yaml") for n in names)
    assert any(n.endswith("data/local.duckdb") for n in names)
    # Artifacts + logs excluded by default
    assert not any("artifacts/stale.txt" in n for n in names)
    assert not any("logs/old.log" in n for n in names)


def test_backup_include_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    (tmp_path / "workspace" / "artifacts" / "keep.txt").write_text("keep me")

    runner.invoke(
        main,
        [
            "backup",
            "--config",
            str(tmp_path / "config" / "workspace.yaml"),
            "--to",
            str(tmp_path / "backups"),
            "--include-artifacts",
        ],
    )
    import tarfile

    archive = next((tmp_path / "backups").glob("*.tar.gz"))
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert any("artifacts/keep.txt" in n for n in names)


def test_backup_then_restore_round_trip(tmp_path: Path) -> None:
    runner = CliRunner()
    src = tmp_path / "src"
    runner.invoke(main, ["init", "--path", str(src)])
    (src / "workspace" / "notebooks" / "demo.py").write_text("# demo\n")

    backup_dir = tmp_path / "backups"
    out = runner.invoke(
        main,
        [
            "backup",
            "--config",
            str(src / "config" / "workspace.yaml"),
            "--to",
            str(backup_dir),
        ],
    )
    assert out.exit_code == 0
    archive = next(backup_dir.glob("*.tar.gz"))

    dst = tmp_path / "dst"
    dst.mkdir()
    out = runner.invoke(main, ["restore", str(archive), "--into", str(dst)])
    assert out.exit_code == 0, out.output
    assert (dst / "workspace" / "notebooks" / "demo.py").read_text() == "# demo\n"


def test_restore_refuses_overwrite_without_force(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--path", str(tmp_path)])
    (tmp_path / "workspace" / "notebooks" / "n.py").write_text("# original\n")
    backup_dir = tmp_path / "backups"
    runner.invoke(
        main,
        [
            "backup",
            "--config",
            str(tmp_path / "config" / "workspace.yaml"),
            "--to",
            str(backup_dir),
        ],
    )
    archive = next(backup_dir.glob("*.tar.gz"))
    # Restore into the same tree — file already exists.
    out = runner.invoke(main, ["restore", str(archive), "--into", str(tmp_path)])
    assert out.exit_code != 0
    assert "exists" in out.output
