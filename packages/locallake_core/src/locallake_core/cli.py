# SPDX-License-Identifier: Apache-2.0
"""LocalLake CLI (``lake``)."""

from __future__ import annotations

import shutil
import tarfile
from datetime import UTC, datetime
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


@main.command()
@click.option(
    "--config",
    "config_path",
    default="config/workspace.yaml",
    type=click.Path(dir_okay=False),
)
@click.option(
    "--to",
    "out_dir",
    default="./backups",
    help="Directory to write the archive into (default: ./backups)",
    type=click.Path(file_okay=False),
)
@click.option(
    "--include-artifacts",
    is_flag=True,
    default=False,
    help="Include workspace/artifacts and workspace/logs. Off by default — they're "
    "reproducible and can be large.",
)
def backup(config_path: str, out_dir: str, include_artifacts: bool) -> None:
    """Bundle config + notebooks + databases into a single tar.gz archive.

    Skips artifacts + logs unless --include-artifacts. The archive is portable:
    `lake restore` on a fresh machine will recreate the workspace.
    """
    from locallake_core.config import LakehouseConfig

    cfg_file = Path(config_path)
    if not cfg_file.exists():
        click.secho(f"  [missing] {config_path}", fg="red")
        raise SystemExit(1)
    cfg = LakehouseConfig.from_file(cfg_file)

    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = target / f"locallake-{cfg.workspace.name}-{ts}.tar.gz"

    workspace_root = Path(cfg.workspace.root_path)
    db_path = Path(cfg.database.path)
    meta_db = Path(cfg.database.path).with_name("metadata.sqlite")
    skip_dirs = (
        {Path(cfg.paths.artifacts).resolve(), Path(cfg.paths.logs).resolve()}
        if not include_artifacts
        else set()
    )

    def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        # tarfile passes paths relative to the archive root; we work in absolute
        # space via the closure's known dirs.
        candidate = (Path(info.name)).resolve()
        for skip in skip_dirs:
            try:
                candidate.relative_to(skip)
                return None
            except ValueError:
                continue
        return info

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(cfg_file, arcname=f"config/{cfg_file.name}")
        if workspace_root.is_dir():
            for entry in sorted(workspace_root.rglob("*")):
                if not entry.is_file():
                    continue
                rel = entry.relative_to(workspace_root.parent)
                if not include_artifacts:
                    try:
                        # Skip anything under artifacts/ or logs/.
                        entry.resolve().relative_to(Path(cfg.paths.artifacts).resolve())
                        continue
                    except ValueError:
                        pass
                    try:
                        entry.resolve().relative_to(Path(cfg.paths.logs).resolve())
                        continue
                    except ValueError:
                        pass
                tar.add(entry, arcname=str(rel))
        for path in (db_path, meta_db):
            if path.is_file():
                tar.add(path, arcname=f"data/{path.name}")

    click.secho(f"  wrote {archive} ({archive.stat().st_size // 1024} KB)", fg="green")
    if not include_artifacts:
        click.echo("  (artifacts + logs skipped; pass --include-artifacts to bundle them)")


@main.command()
@click.argument("archive_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--into",
    "target_dir",
    default=".",
    help="Directory to restore into (default: current dir).",
    type=click.Path(file_okay=False),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing files. Off by default to avoid clobbering live state.",
)
def restore(archive_path: str, target_dir: str, force: bool) -> None:
    """Restore a workspace from a `lake backup` archive."""
    archive = Path(archive_path)
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        # Reject any member path that escapes the target after resolution. This
        # is the "tarfile filter" pattern Python 3.12 adds for security.
        for m in members:
            dest = (target / m.name).resolve()
            try:
                dest.relative_to(target)
            except ValueError:
                click.secho(f"  refusing path traversal: {m.name}", fg="red")
                raise SystemExit(1) from None
            if dest.exists() and not force:
                click.secho(f"  [exists] {m.name} (pass --force to overwrite)", fg="yellow")
                raise SystemExit(1)
        tar.extractall(target, filter="data")

    click.secho(f"  restored {len(members)} entries into {target}", fg="green")


if __name__ == "__main__":
    main()
