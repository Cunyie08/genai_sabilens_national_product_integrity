from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, get_tenant_ctx
from backend.admin.services.metrics_service import (
    get_overview,
    get_trend,
    get_product_breakdown,
    get_top_markets,
    get_state_breakdown,
)
from backend.admin.cache import cache_response
from backend.utils.response import success_response

router = APIRouter()


@router.get("/metrics/overview")
@cache_response(ttl=120, key_prefix="admin:overview")
async def overview(
    period_days: int = Query(30, ge=1, le=365),
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_overview(db, ctx, period_days)
    return success_response(data.model_dump())


@router.get("/metrics/trends")
@cache_response(ttl=300, key_prefix="admin:trends")
async def trends(
    granularity: Literal["daily", "weekly", "monthly"] = Query("daily"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_trend(db, ctx, granularity, date_from, date_to)
    return success_response(data.model_dump())


@router.get("/metrics/products")
async def products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_product_breakdown(db, ctx, page, per_page)
    return success_response(data.model_dump())


@router.get("/metrics/top-markets")
@cache_response(ttl=120, key_prefix="admin:markets")
async def top_markets(
    limit: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_top_markets(db, ctx, limit)
    return success_response(data.model_dump())


@router.get("/metrics/states")
@cache_response(ttl=120, key_prefix="admin:states")
async def state_breakdown(
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_state_breakdown(db, ctx)
    return success_response(data.model_dump())
