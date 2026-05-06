"""
Super Admin routes — /api/v1/admin/super/*

Restricted to super_admin role only.
Full unrestricted access across all companies, all states.
"""
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, require_super_admin
from backend.admin.models import EnforcementCase
from backend.admin.schemas.heatmap import HeatmapFilters
from backend.admin.schemas.reports import ReportTriggerRequest
from backend.admin.schemas.enforcement import CaseUpdateRequest
from backend.admin.schemas.access_requests import AccessRequestReview
from backend.admin.services.heatmap_service import get_heatmap
from backend.admin.services.metrics_service import (
    get_overview,
    get_trend,
    get_product_breakdown,
    get_top_markets,
    get_state_breakdown,
)
from backend.admin.services.report_service import (
    trigger_report, get_report_status, list_reports,
)
from backend.admin.services.enforcement_service import (
    list_cases, update_case, get_raid_candidates, _to_response,
)
from backend.admin.services.access_request_service import (
    list_all_requests, approve_request, reject_request, revoke_request,
)
from backend.models.user import User, UserRole
from backend.admin.cache import cache_response
from backend.utils.response import success_response

router = APIRouter(tags=["Super Admin"])


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics/overview")
@cache_response(ttl=120, key_prefix="super:overview")
async def overview(
    period_days: int = Query(30, ge=1, le=365),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_overview(db, ctx, period_days)
    return success_response(data.model_dump())


@router.get("/metrics/trends")
@cache_response(ttl=300, key_prefix="super:trends")
async def trends(
    granularity: Literal["daily", "weekly", "monthly"] = Query("daily"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_trend(db, ctx, granularity, date_from, date_to)
    return success_response(data.model_dump())


@router.get("/metrics/products")
async def products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_product_breakdown(db, ctx, page, per_page)
    return success_response(data.model_dump())


@router.get("/metrics/top-markets")
@cache_response(ttl=120, key_prefix="super:markets")
async def top_markets(
    limit: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_top_markets(db, ctx, limit)
    return success_response(data.model_dump())


@router.get("/metrics/states")
@cache_response(ttl=120, key_prefix="super:states")
async def state_breakdown(
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_state_breakdown(db, ctx)
    return success_response(data.model_dump())


# ── Heatmap (global — state-level by default, LGA drill-down via ?state=X) ───

@router.get("/heatmap")
@cache_response(ttl=60, key_prefix="super:heatmap")
async def heatmap(
    state:       str | None  = Query(None, description="Drill down to LGA level for a specific state"),
    subcategory: str | None  = Query(None),
    date_from:   date | None = Query(None),
    date_to:     date | None = Query(None),
    ctx: TenantContext  = Depends(require_super_admin),
    db: AsyncSession    = Depends(get_db),
):
    filters = HeatmapFilters(
        state=state,
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
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await list_cases(db, ctx, page, per_page, status)
    return success_response(data.model_dump())


@router.get("/enforcement/cases/{case_id}")
async def case_detail(
    case_id: UUID,
    ctx: TenantContext = Depends(require_super_admin),
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
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await update_case(db, ctx, case_id, payload)
    return success_response(data.model_dump())


@router.get("/enforcement/raid-candidates")
async def raid_candidates(
    min_risk_score: float = Query(0.75, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_raid_candidates(db, ctx, min_risk_score, limit)
    return success_response(data.model_dump())


# ── NAFDAC Access Request Queue ───────────────────────────────────────────────

@router.get("/access-requests")
async def access_request_queue(
    status: str | None = Query("pending", description="pending | approved | rejected | revoked"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await list_all_requests(db, ctx, status_filter=status, page=page, per_page=per_page)
    return success_response(data.model_dump())


@router.patch("/access-requests/{request_id}/approve")
async def approve(
    request_id: UUID,
    payload: AccessRequestReview,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await approve_request(db, ctx, request_id, payload)
    return success_response(data.model_dump())


@router.patch("/access-requests/{request_id}/reject")
async def reject(
    request_id: UUID,
    payload: AccessRequestReview,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await reject_request(db, ctx, request_id, payload)
    return success_response(data.model_dump())


@router.patch("/access-requests/{request_id}/revoke")
async def revoke(
    request_id: UUID,
    payload: AccessRequestReview,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await revoke_request(db, ctx, request_id, payload)
    return success_response(data.model_dump())


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports")
async def report_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await list_reports(db, ctx, page, per_page)
    return success_response(data.model_dump())


@router.post("/reports/trigger")
async def trigger(
    payload: ReportTriggerRequest,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await trigger_report(db, ctx, payload)
    return success_response(data.model_dump())


@router.get("/reports/{report_id}")
async def report_status(
    report_id: UUID,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await get_report_status(db, ctx, report_id)
    return success_response(data.model_dump())


# ── User Management ───────────────────────────────────────────────────────────

class RoleUpdateRequest(BaseModel):
    role: UserRole
    state: Optional[str] = None   # required when promoting to nafdac_admin / nafdac_officer


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    stmt = select(User).where(User.deleted_at.is_(None))
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)

    count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    if role:
        count_stmt = count_stmt.where(User.role == role)

    users = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    return success_response({
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "phone": u.phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "status": u.status,
                "state": u.state,
                "company_id": str(u.company_id) if u.company_id else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
    })


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    body: RoleUpdateRequest,
    ctx: TenantContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == ctx.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own role.")

    target = (await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    new_role = str(body.role.value if hasattr(body.role, "value") else body.role)

    # Prevent total super_admin lockout
    if target.role == "super_admin" and new_role != "super_admin":
        count = (await db.execute(
            select(func.count()).select_from(User).where(
                User.role == "super_admin",
                User.deleted_at.is_(None),
                User.status == "active",
            )
        )).scalar_one()
        if count <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot demote the last active super_admin. Promote another user first.",
            )

    # Require state when assigning NAFDAC roles
    nafdac_roles = {"nafdac_admin", "nafdac_officer"}
    if new_role in nafdac_roles and not body.state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A jurisdiction state is required when assigning a NAFDAC role.",
        )

    old_role = target.role
    target.role = new_role
    if body.state:
        target.state = body.state

    await db.commit()
    await db.refresh(target)

    return success_response({
        "id": str(target.id),
        "email": target.email,
        "role": target.role,
        "state": target.state,
        "message": f"Role updated from {old_role} to {new_role}",
    })
