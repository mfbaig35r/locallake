# SPDX-License-Identifier: Apache-2.0
"""Artifact list / download / parquet preview endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from locallake_core.config import LakehouseConfig
from locallake_core.models import JobRun


def _seed_run(factory: Any, *, notebook_path: str = "x.py", status: str = "success") -> str:
    s = factory()
    try:
        r = JobRun(
            notebook_path=notebook_path,
            status=status,
            created_at=datetime.now(UTC),
            triggered_by="test",
            parameters_json="{}",
            timeout_seconds=60,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _artifact_root(cfg: LakehouseConfig, job_id: str) -> Path:
    root = Path(cfg.paths.artifacts) / "runs" / job_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_list_artifacts_empty_when_no_files(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    _artifact_root(lake_config, job_id)  # dir exists but empty
    res = client.get(f"/jobs/{job_id}/artifacts")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_artifacts_returns_files_recursively(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    (root / "a.txt").write_text("hello")
    (root / "sub").mkdir()
    (root / "sub" / "b.parquet").write_bytes(b"\x00" * 100)

    res = client.get(f"/jobs/{job_id}/artifacts")
    assert res.status_code == 200
    body = res.json()
    paths = {it["path"] for it in body["items"]}
    assert paths == {"a.txt", "sub/b.parquet"}
    by_path = {it["path"]: it for it in body["items"]}
    assert by_path["sub/b.parquet"]["previewable"] is True
    assert by_path["a.txt"]["previewable"] is False


def test_list_artifacts_404_for_unknown_job(client: Any) -> None:
    res = client.get("/jobs/does-not-exist/artifacts")
    assert res.status_code == 404


def test_download_artifact_streams_file(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    (root / "data.csv").write_text("a,b\n1,2\n")
    res = client.get(f"/jobs/{job_id}/artifacts/data.csv")
    assert res.status_code == 200
    assert res.content == b"a,b\n1,2\n"


def test_download_rejects_path_traversal(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    _artifact_root(lake_config, job_id)
    res = client.get(f"/jobs/{job_id}/artifacts/../escape.txt")
    # FastAPI normalizes `..` segments before routing, so this lands as 404
    # rather than reaching our handler; either way we never read outside root.
    assert res.status_code in {400, 404}


@pytest.fixture
def parquet_root(lake_config: LakehouseConfig, session_factory: Any) -> tuple[str, Path]:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    parquet_path = root / "out.parquet"
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            "COPY (SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) t(id, name)) "
            f"TO '{parquet_path}' (FORMAT PARQUET)"
        )
    finally:
        conn.close()
    return job_id, parquet_path


def test_preview_parquet_returns_rows_and_count(
    client: Any, parquet_root: tuple[str, Path]
) -> None:
    job_id, _ = parquet_root
    res = client.get(f"/jobs/{job_id}/artifacts/out.parquet/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["total_rows"] == 3
    assert body["truncated"] is False
    assert "id" in body["columns"]
    assert "name" in body["columns"]
    assert len(body["rows"]) == 3


def test_preview_truncates_to_requested_rows(client: Any, parquet_root: tuple[str, Path]) -> None:
    job_id, _ = parquet_root
    res = client.get(f"/jobs/{job_id}/artifacts/out.parquet/preview?rows=1")
    assert res.status_code == 200
    body = res.json()
    assert len(body["rows"]) == 1
    assert body["truncated"] is True


def test_preview_415_for_non_parquet(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    (root / "notes.txt").write_text("plain")
    res = client.get(f"/jobs/{job_id}/artifacts/notes.txt/preview")
    assert res.status_code == 415


def test_list_marks_images_as_previewable(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    (root / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    (root / "notes.txt").write_text("plain")
    res = client.get(f"/jobs/{job_id}/artifacts")
    by_path = {it["path"]: it for it in res.json()["items"]}
    assert by_path["chart.png"]["previewable"] is True
    assert by_path["notes.txt"]["previewable"] is False


def test_raw_image_returns_correct_mime(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    body = b"\x89PNG\r\n\x1a\nbody"
    (root / "chart.png").write_bytes(body)
    res = client.get(f"/jobs/{job_id}/artifacts/chart.png/raw")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")
    assert res.content == body


def test_preview_415_for_image(
    client: Any, session_factory: Any, lake_config: LakehouseConfig
) -> None:
    """Image suffixes are previewable in the list, but /preview is parquet-only.
    The UI dispatches images to /raw + an <img> instead.
    """
    job_id = _seed_run(session_factory)
    root = _artifact_root(lake_config, job_id)
    (root / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    res = client.get(f"/jobs/{job_id}/artifacts/chart.png/preview")
    assert res.status_code == 415
