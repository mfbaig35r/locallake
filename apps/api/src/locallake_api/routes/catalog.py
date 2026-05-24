# SPDX-License-Identifier: Apache-2.0
"""Catalog routes — schema browser over the workspace DuckDB."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from locallake_core.catalog import describe_table, list_tables, sample_table
from locallake_core.config import LakehouseConfig

from locallake_api.deps import get_config
from locallake_api.schemas import (
    ColumnEntryOut,
    TableDetailOut,
    TableEntryOut,
    TableListOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/tables", response_model=TableListOut)
async def list_tables_endpoint(
    cfg: LakehouseConfig = Depends(get_config),
) -> TableListOut:
    entries = list_tables(cfg.database.path)
    items = [TableEntryOut(schema_name=e.schema, name=e.name, kind=e.kind) for e in entries]
    return TableListOut(items=items, total=len(items))


@router.get("/tables/{schema_name}/{name}", response_model=TableDetailOut)
async def get_table_detail(
    schema_name: str,
    name: str,
    sample_rows: int = Query(default=50, ge=0, le=500),
    cfg: LakehouseConfig = Depends(get_config),
) -> TableDetailOut:
    try:
        detail = describe_table(cfg.database.path, schema_name, name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if detail is None:
        raise HTTPException(404, f"table not found: {schema_name}.{name}")

    if sample_rows > 0:
        try:
            sample_cols, sample = sample_table(
                cfg.database.path, schema_name, name, limit=sample_rows
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    else:
        sample_cols, sample = [], []

    return TableDetailOut(
        schema_name=detail.schema,
        name=detail.name,
        kind=detail.kind,
        columns=[
            ColumnEntryOut(name=c.name, type=c.type, nullable=c.nullable) for c in detail.columns
        ],
        row_count=detail.row_count,
        sample_columns=sample_cols,
        sample_rows=sample,
    )
