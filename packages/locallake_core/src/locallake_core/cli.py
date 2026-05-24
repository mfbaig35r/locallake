# SPDX-License-Identifier: Apache-2.0
"""LocalLake CLI (``lake``)."""

from __future__ import annotations

import shutil
from importlib import metadata, resources
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


def _seed_templates(target_dir: Path) -> list[str]:
    """Copy the package-bundled starter templates into ``target_dir``.

    Returns the names of templates that were copied (existing ones are left
    alone so user edits are not clobbered on re-init).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    source = resources.files("locallake_core._templates")
    for entry in source.iterdir():
        if not entry.name.endswith(".py") or entry.name == "__init__.py":
            continue
        dest = target_dir / entry.name
        if dest.exists():
            continue
        dest.write_text(entry.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(entry.name)
    return copied


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

    seeded = _seed_templates(workspace_dir / "templates")
    if seeded:
        click.echo(f"Seeded templates: {', '.join(seeded)}")

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


@main.command()
@click.option(
    "--config",
    "config_path",
    default="config/workspace.yaml",
    type=click.Path(dir_okay=False),
)
def start(config_path: str) -> None:
    """Print the dev start commands for the local API + worker + web."""
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        click.secho(f"  [missing] {config_path}", fg="red")
        click.echo("    Run `lake init` first.")
        raise SystemExit(1)
    click.echo("Start the three services in separate terminals:")
    click.echo("")
    click.echo(
        "  uv run --package locallake-api uvicorn locallake_api.main:app --reload --port 8000"
    )
    click.echo("  uv run --package locallake-worker arq locallake_worker.main.WorkerSettings")
    click.echo("  cd apps/web && pnpm dev")
    click.echo("")
    click.echo("Then open http://localhost:3000")


@main.command()
@click.option(
    "--config",
    "config_path",
    default="config/workspace.yaml",
    type=click.Path(dir_okay=False),
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip the confirmation prompt",
)
def reset(config_path: str, yes: bool) -> None:
    """Clear run logs + artifacts + run history. Notebooks + workspace DB are kept."""
    from locallake_core.config import LakehouseConfig

    cfg_file = Path(config_path)
    if not cfg_file.exists():
        click.secho(f"  [missing] {config_path}", fg="red")
        raise SystemExit(1)

    cfg = LakehouseConfig.from_file(cfg_file)
    targets = [
        ("logs", Path(cfg.paths.logs)),
        ("artifacts", Path(cfg.paths.artifacts)),
    ]

    click.echo("This will delete:")
    for label, path in targets:
        click.echo(f"  - {label}: {path}")
    if not yes and not click.confirm("Continue?", default=False):
        click.echo("aborted")
        return

    for label, path in targets:
        if not path.exists():
            continue
        for entry in path.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        click.secho(f"  cleared {label}", fg="green")
    click.echo("done")


if __name__ == "__main__":
    main()
