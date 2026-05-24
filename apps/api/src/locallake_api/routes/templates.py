# SPDX-License-Identifier: Apache-2.0
"""Template routes — list notebook starter templates."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from locallake_core.config import LakehouseConfig
from locallake_core.templates import list_templates

from locallake_api.deps import get_config
from locallake_api.schemas import TemplateEntryOut, TemplateListOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListOut)
async def list_templates_endpoint(
    cfg: LakehouseConfig = Depends(get_config),
) -> TemplateListOut:
    entries = list_templates(cfg)
    items = [
        TemplateEntryOut(
            name=e.name,
            size_bytes=e.size_bytes,
            last_modified=e.last_modified,
        )
        for e in entries
    ]
    return TemplateListOut(items=items, total=len(items))
