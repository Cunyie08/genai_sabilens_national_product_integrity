from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, get_tenant_ctx, require_nafdac_or_super
from backend.admin.models import EnforcementCase
from backend.admin.schemas.enforcement import CaseUpdateRequest
from backend.admin.services.enforcement_service import (
    list_cases,
    update_case,
    get_raid_candidates,
    _to_response,
)
from backend.utils.response import success_response

router = APIRouter()


@router.get("/enforcement/cases")
async def cases(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_nafdac_or_super),
    db: AsyncSession = Depends(get_db),
):
    data = await list_cases(db, ctx, page, per_page, status)
    return success_response(data.model_dump())


@router.get("/enforcement/cases/{case_id}")
async def case_detail(
    case_id: UUID,
    ctx: TenantContext = Depends(require_nafdac_or_super),
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
    ctx: TenantContext = Depends(require_nafdac_or_super),
    db: AsyncSession = Depends(get_db),
):
    data = await update_case(db, ctx, case_id, payload)
    return success_response(data.model_dump())


@router.get("/enforcement/raid-candidates")
async def raid_candidates(
    min_risk_score: float = Query(0.75, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require_nafdac_or_super),
    db: AsyncSession = Depends(get_db),
):
    data = await get_raid_candidates(db, ctx, min_risk_score, limit)
    return success_response(data.model_dump())
