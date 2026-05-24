# SPDX-License-Identifier: Apache-2.0
"""LocalLake CLI (``lake``)."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import click

WORKSPACE_TEMPLATE = """\
workspace:
  name: {name}
  root_path: {root}
database:
  type: duckdb
  path: {db_path}
paths:
  notebooks: {notebooks}
  artifacts: {artifacts}
  logs: {logs}
  templates: {templates}
"""


@click.group()
@click.version_option(version=metadata.version("locallake-core"))
def main() -> None:
    """LocalLake CLI."""


@main.command()
@click.option("--name", default="my-locallake", help="Workspace name")
@click.option(
    "--path",
    "path_",
    default=".",
    help="Where to scaffold (default: current directory)",
    type=click.Path(file_okay=False, resolve_path=True),
)
def init(name: str, path_: str) -> None:
    """Scaffold a new LocalLake workspace at the given directory."""
    root = Path(path_)
    root.mkdir(parents=True, exist_ok=True)

    config_dir = root / "config"
    workspace_dir = root / "workspace"
    data_dir = root / "data"

    for d in [
        config_dir,
        workspace_dir / "notebooks",
        workspace_dir / "artifacts",
        workspace_dir / "logs",
        workspace_dir / "templates",
        data_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "workspace.yaml"
    if config_file.exists():
        click.echo(f"Config already exists at {config_file}, leaving as-is.")
    else:
        config_file.write_text(
            WORKSPACE_TEMPLATE.format(
                name=name,
                root=str(workspace_dir),
                db_path=str(data_dir / "local.duckdb"),
                notebooks=str(workspace_dir / "notebooks"),
                artifacts=str(workspace_dir / "artifacts"),
                logs=str(workspace_dir / "logs"),
                templates=str(workspace_dir / "templates"),
            ),
            encoding="utf-8",
        )
        click.echo(f"Wrote {config_file}")

    click.echo("")
    click.echo(f"LocalLake workspace ready at {root}")
    click.echo("")
    click.echo("Next:")
    click.echo(f"  cd {root}")
    click.echo("  docker compose up         # or run services manually with uv run")
    click.echo("  open http://localhost:3000")


@main.command()
@click.option(
    "--config",
    "config_path",
    default="config/workspace.yaml",
    type=click.Path(dir_okay=False),
)
def doctor(config_path: str) -> None:
    """Diagnose common setup issues."""
    from locallake_core.config import LakehouseConfig

    ok = True
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        click.secho(f"  [missing] {config_path}", fg="red")
        click.echo("    Run `lake init` first.")
        raise SystemExit(1)

    try:
        cfg = LakehouseConfig.from_file(cfg_file)
        click.secho(f"  [ok] config valid ({cfg.workspace.name})", fg="green")
    except Exception as exc:
        click.secho(f"  [invalid] {config_path}: {exc}", fg="red")
        raise SystemExit(1) from exc

    for label, p in [
        ("workspace.root_path", cfg.workspace.root_path),
        ("paths.notebooks", cfg.paths.notebooks),
        ("paths.artifacts", cfg.paths.artifacts),
        ("paths.logs", cfg.paths.logs),
        ("paths.templates", cfg.paths.templates),
    ]:
        if Path(p).exists():
            click.secho(f"  [ok] {label} exists ({p})", fg="green")
        else:
            click.secho(f"  [missing] {label} ({p})", fg="yellow")
            ok = False

    db_parent = Path(cfg.database.path).parent
    if db_parent.exists():
        click.secho(f"  [ok] database parent exists ({db_parent})", fg="green")
    else:
        click.secho(f"  [missing] database parent ({db_parent})", fg="yellow")
        ok = False

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
