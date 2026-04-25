"""Report trigger, status, and signed URL management."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.dependencies import TenantContext
from backend.admin.models import AdminReport
from backend.admin.schemas.reports import (
    ReportTriggerRequest,
    ReportTriggerResponse,
    ReportStatusResponse,
    ReportListResponse,
    ReportListItem,
)
from backend.config import settings


async def trigger_report(
    db: AsyncSession,
    ctx: TenantContext,
    payload: ReportTriggerRequest,
) -> ReportTriggerResponse:
    from backend.admin.tasks import generate_report

    report = AdminReport(
        company_id=ctx.company_id,
        requested_by_user_id=ctx.user_id,
        report_type=payload.report_type,
        filter_state=payload.filter_state,
        filter_lga=payload.filter_lga,
        filter_subcategory_id=payload.filter_subcategory_id,
        filter_date_from=payload.filter_date_from,
        filter_date_to=payload.filter_date_to,
        status="queued",
    )
    db.add(report)
    await db.flush()

    task = generate_report.delay(str(report.id))
    report.task_id = task.id
    await db.commit()

    return ReportTriggerResponse(
        report_id=report.id,
        company_id=report.company_id,
        task_id=task.id,
        status="queued",
        message="Report generation queued. Poll GET /reports/{report_id} for status.",
    )


async def get_report_status(
    db: AsyncSession,
    ctx: TenantContext,
    report_id: UUID,
) -> ReportStatusResponse:
    result = await db.execute(select(AdminReport).where(AdminReport.id == report_id))
    report: AdminReport | None = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    ctx.assert_report_owner(report)

    pdf_url: str | None = None
    pdf_expires_at: datetime | None = None

    if report.status == "ready" and report.gcs_key:
        now = datetime.now(timezone.utc)
        needs_refresh = (
            report.signed_url is None
            or report.signed_url_expires_at is None
            or report.signed_url_expires_at <= now + timedelta(minutes=5)
        )
        if needs_refresh:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(settings.GCS_REPORTS_BUCKET)
            blob = bucket.blob(report.gcs_key)
            expires = now + timedelta(minutes=15)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),
                method="GET",
            )
            report.signed_url = url
            report.signed_url_expires_at = expires
            await db.commit()

        pdf_url = report.signed_url
        pdf_expires_at = report.signed_url_expires_at

    return ReportStatusResponse(
        report_id=report.id,
        report_type=report.report_type,
        status=report.status,
        pdf_url=pdf_url,
        pdf_expires_at=pdf_expires_at,
        report_json=report.report_json,
        generated_at=report.generated_at,
        error_message=report.error_message,
        created_at=report.created_at,
    )


async def list_reports(
    db: AsyncSession,
    ctx: TenantContext,
    page: int = 1,
    per_page: int = 20,
) -> ReportListResponse:
    offset = (page - 1) * per_page

    stmt = select(AdminReport).order_by(AdminReport.created_at.desc())
    stmt = ctx.apply_report_filter(stmt)
    stmt = stmt.offset(offset).limit(per_page)

    count_stmt = select(sqlfunc.count()).select_from(AdminReport)
    count_stmt = ctx.apply_report_filter(count_stmt)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    return ReportListResponse(
        items=[
            ReportListItem(
                report_id=r.id,
                report_type=r.report_type,
                status=r.status,
                generated_at=r.generated_at,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        per_page=per_page,
    )
