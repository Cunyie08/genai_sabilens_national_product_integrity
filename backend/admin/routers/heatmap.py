from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, get_tenant_ctx
from backend.admin.schemas.heatmap import HeatmapFilters
from backend.admin.services.heatmap_service import get_heatmap
from backend.admin.cache import cache_response
from backend.utils.response import success_response

router = APIRouter()


@router.get("/heatmap", response_model=None)
@cache_response(ttl=60, key_prefix="admin:heatmap")
async def heatmap_endpoint(
    state:       str | None  = Query(None, description="Super Admin drill-down: filter to one state"),
    lga:         str | None  = Query(None),
    subcategory: str | None  = Query(None, description="nafdac_chunks.json subcategory slug"),
    date_from:   date | None = Query(None),
    date_to:     date | None = Query(None),
    ctx: TenantContext    = Depends(get_tenant_ctx),
    db:  AsyncSession     = Depends(get_db),
):
    filters = HeatmapFilters(
        state=state,
        lga=lga,
        subcategory=subcategory,
        date_from=date_from,
        date_to=date_to,
    )
    data = await get_heatmap(db, ctx, filters)
    return success_response(data.model_dump())
