"""
NAFDAC Admin routes — /api/v1/admin/nafdac/*

Restricted to nafdac_admin and nafdac_officer roles.
TenantContext automatically geofences every scan query to user.state (jurisdiction).
Brand/quantity data is gated behind an approved NafdacAccessRequest.
"""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, require_nafdac
from backend.admin.models import EnforcementCase
from backend.admin.schemas.heatmap import HeatmapFilters
from backend.admin.schemas.enforcement import CaseUpdateRequest
from backend.admin.schemas.access_requests import AccessRequestCreate, AccessRequestReview
from backend.admin.services.heatmap_service import get_heatmap
from backend.admin.services.metrics_service import get_overview, get_trend
from backend.admin.services.enforcement_service import (
    list_cases, update_case, get_raid_candidates, _to_response,
)
from backend.admin.services.access_request_service import (
    create_request, list_own_requests, withdraw_request,
)
from backend.admin.cache import cache_response
from backend.utils.response import success_response

router = APIRouter(tags=["NAFDAC Admin"])


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics/overview")
@cache_response(ttl=120, key_prefix="nafdac:overview")
async def overview(
    period_days: int = Query(30, ge=1, le=365),
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await get_overview(db, ctx, period_days)
    return success_response(data.model_dump())


@router.get("/metrics/trends")
@cache_response(ttl=300, key_prefix="nafdac:trends")
async def trends(
    granularity: Literal["daily", "weekly", "monthly"] = Query("daily"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await get_trend(db, ctx, granularity, date_from, date_to)
    return success_response(data.model_dump())


# ── Heatmap (LGA-level, jurisdiction-geofenced) ───────────────────────────────

@router.get("/heatmap")
@cache_response(ttl=60, key_prefix="nafdac:heatmap")
async def heatmap(
    subcategory: str | None  = Query(None),
    date_from:   date | None = Query(None),
    date_to:     date | None = Query(None),
    ctx: TenantContext  = Depends(require_nafdac),
    db: AsyncSession    = Depends(get_db),
):
    # state is intentionally excluded — NAFDAC jurisdiction is auto-applied by TenantContext
    filters = HeatmapFilters(
        subcategory=subcategory,
        date_from=date_from,
        date_to=date_to,
    )
    data = await get_heatmap(db, ctx, filters)
    return success_response(data.model_dump())


# ── Enforcement ───────────────────────────────────────────────────────────────

@router.get("/enforcement/cases")
async def cases(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await list_cases(db, ctx, page, per_page, status)
    return success_response(data.model_dump())


@router.get("/enforcement/cases/{case_id}")
async def case_detail(
    case_id: UUID,
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EnforcementCase).where(EnforcementCase.id == case_id))
    enforcement_case = result.scalar_one_or_none()
    if enforcement_case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = await _to_response(db, enforcement_case)
    return success_response(data.model_dump())


@router.patch("/enforcement/cases/{case_id}")
async def update_case_endpoint(
    case_id: UUID,
    payload: CaseUpdateRequest,
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await update_case(db, ctx, case_id, payload)
    return success_response(data.model_dump())


@router.get("/enforcement/raid-candidates")
async def raid_candidates(
    min_risk_score: float = Query(0.75, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await get_raid_candidates(db, ctx, min_risk_score, limit)
    return success_response(data.model_dump())


# ── Access Requests ───────────────────────────────────────────────────────────

@router.get("/access-requests")
async def my_access_requests(
    status: str | None = Query(None, description="pending | approved | rejected | revoked"),
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await list_own_requests(db, ctx, status_filter=status)
    return success_response(data.model_dump())


@router.post("/access-requests")
async def submit_access_request(
    payload: AccessRequestCreate,
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    data = await create_request(db, ctx, payload)
    return success_response(data.model_dump())


@router.delete("/access-requests/{request_id}", status_code=204)
async def withdraw_access_request(
    request_id: UUID,
    ctx: TenantContext = Depends(require_nafdac),
    db: AsyncSession = Depends(get_db),
):
    await withdraw_request(db, ctx, request_id)
