from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.admin.dependencies import TenantContext, get_tenant_ctx
from backend.admin.schemas.reports import ReportTriggerRequest
from backend.admin.services.report_service import trigger_report, get_report_status, list_reports
from backend.utils.response import success_response

router = APIRouter()


@router.post("/reports/trigger")
async def trigger(
    payload: ReportTriggerRequest,
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await trigger_report(db, ctx, payload)
    return success_response(data.model_dump())


@router.get("/reports/{report_id}")
async def report_status(
    report_id: UUID,
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await get_report_status(db, ctx, report_id)
    return success_response(data.model_dump())


@router.get("/reports")
async def report_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant_ctx),
    db: AsyncSession = Depends(get_db),
):
    data = await list_reports(db, ctx, page, per_page)
    return success_response(data.model_dump())
