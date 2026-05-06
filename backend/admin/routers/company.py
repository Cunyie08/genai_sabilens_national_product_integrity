"""
Company Admin routes — /api/v1/admin/company/*

All endpoints are restricted to company_admin role.
TenantContext.apply_scan_filter() automatically scopes every query
to the caller's company_id (derived from JWT — never the request body).
"""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, require_company_admin
from backend.admin.schemas.heatmap import HeatmapFilters
from backend.admin.schemas.reports import ReportTriggerRequest
from backend.admin.services.heatmap_service import get_heatmap
from backend.admin.services.metrics_service import (
    get_overview,
    get_trend,
    get_product_breakdown,
    get_top_markets,
    get_state_breakdown,
)
from backend.admin.services.report_service import (
    trigger_report,
    get_report_status,
    list_reports,
)
from backend.admin.cache import cache_response
from backend.utils.response import success_response

router = APIRouter(tags=["Company Admin"])


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics/overview")
@cache_response(ttl=120, key_prefix="company:overview")
async def overview(
    period_days: int = Query(30, ge=1, le=365),
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_overview(db, ctx, period_days)
    return success_response(data.model_dump())


@router.get("/metrics/trends")
@cache_response(ttl=300, key_prefix="company:trends")
async def trends(
    granularity: Literal["daily", "weekly", "monthly"] = Query("daily"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_trend(db, ctx, granularity, date_from, date_to)
    return success_response(data.model_dump())


@router.get("/metrics/products")
async def products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_product_breakdown(db, ctx, page, per_page)
    return success_response(data.model_dump())


@router.get("/metrics/top-markets")
@cache_response(ttl=120, key_prefix="company:markets")
async def top_markets(
    limit: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_top_markets(db, ctx, limit)
    return success_response(data.model_dump())


@router.get("/metrics/states")
@cache_response(ttl=120, key_prefix="company:states")
async def state_breakdown(
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_state_breakdown(db, ctx)
    return success_response(data.model_dump())


# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/heatmap")
@cache_response(ttl=60, key_prefix="company:heatmap")
async def heatmap(
    lga:         str | None  = Query(None),
    subcategory: str | None  = Query(None),
    date_from:   date | None = Query(None),
    date_to:     date | None = Query(None),
    ctx: TenantContext  = Depends(require_company_admin),
    db: AsyncSession    = Depends(get_db),
):
    filters = HeatmapFilters(
        lga=lga,
        subcategory=subcategory,
        date_from=date_from,
        date_to=date_to,
    )
    data = await get_heatmap(db, ctx, filters)
    return success_response(data.model_dump())


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports")
async def report_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await list_reports(db, ctx, page, per_page)
    return success_response(data.model_dump())


@router.post("/reports/trigger")
async def trigger(
    payload: ReportTriggerRequest,
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await trigger_report(db, ctx, payload)
    return success_response(data.model_dump())


@router.get("/reports/{report_id}")
async def report_status(
    report_id: UUID,
    ctx: TenantContext = Depends(require_company_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_report_status(db, ctx, report_id)
    return success_response(data.model_dump())
