"""Enforcement case management."""
from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.dependencies import TenantContext
from backend.admin.models import EnforcementCase
from backend.admin.schemas.enforcement import (
    EnforcementCaseResponse,
    EnforcementListResponse,
    CaseUpdateRequest,
)
from backend.models.product import Product
from backend.models.company import Company


async def list_cases(
    db: AsyncSession,
    ctx: TenantContext,
    page: int = 1,
    per_page: int = 20,
    status_filter: str | None = None,
) -> EnforcementListResponse:
    ctx.assert_admin_or_nafdac()

    stmt = select(EnforcementCase).order_by(EnforcementCase.risk_score.desc())
    stmt = ctx.apply_enforcement_filter(stmt)
    if status_filter:
        stmt = stmt.where(EnforcementCase.status == status_filter)

    count_stmt = select(func.count()).select_from(EnforcementCase)
    count_stmt = ctx.apply_enforcement_filter(count_stmt)
    if status_filter:
        count_stmt = count_stmt.where(EnforcementCase.status == status_filter)

    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    product_ids = {r.product_id for r in rows if r.product_id}
    company_ids = {r.company_id for r in rows if r.company_id}

    product_names: dict[UUID, str] = {}
    company_names: dict[UUID, str] = {}

    if product_ids:
        p_rows = (await db.execute(
            select(Product.id, Product.name).where(Product.id.in_(product_ids))
        )).all()
        product_names = {r.id: r.name for r in p_rows}

    if company_ids:
        c_rows = (await db.execute(
            select(Company.id, Company.name).where(Company.id.in_(company_ids))
        )).all()
        company_names = {r.id: r.name for r in c_rows}

    items = [
        EnforcementCaseResponse(
            id=r.id,
            cluster_key=r.cluster_key,
            product_name=product_names.get(r.product_id),
            company_name=company_names.get(r.company_id),
            scan_location_state=r.scan_location_state,
            scan_location_lga=r.scan_location_lga,
            market_name=r.market_name,
            center_latitude=r.center_latitude,
            center_longitude=r.center_longitude,
            fake_scan_count=r.fake_scan_count,
            suspicious_scan_count=r.suspicious_scan_count,
            total_scan_count=r.total_scan_count,
            risk_score=r.risk_score,
            status=r.status,
            assigned_officer_id=r.assigned_officer_id,
            nafdac_case_ref=r.nafdac_case_ref,
            evidence_package=r.evidence_package,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return EnforcementListResponse(items=items, total=total, page=page, per_page=per_page)


async def update_case(
    db: AsyncSession,
    ctx: TenantContext,
    case_id: UUID,
    payload: CaseUpdateRequest,
) -> EnforcementCaseResponse:
    ctx.assert_admin_or_nafdac()

    result = await db.execute(select(EnforcementCase).where(EnforcementCase.id == case_id))
    enforcement_case: EnforcementCase | None = result.scalar_one_or_none()
    if enforcement_case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    if payload.status is not None:
        enforcement_case.status = payload.status
    if payload.assigned_officer_id is not None:
        enforcement_case.assigned_officer_id = payload.assigned_officer_id
    if payload.nafdac_case_ref is not None:
        enforcement_case.nafdac_case_ref = payload.nafdac_case_ref

    await db.commit()
    await db.refresh(enforcement_case)
    return await _to_response(db, enforcement_case)


async def get_raid_candidates(
    db: AsyncSession,
    ctx: TenantContext,
    min_risk_score: float = 0.75,
    limit: int = 50,
) -> EnforcementListResponse:
    """Returns open cases with risk_score >= min_risk_score, ordered by score desc."""
    ctx.assert_admin_or_nafdac()

    stmt = (
        select(EnforcementCase)
        .where(EnforcementCase.risk_score >= min_risk_score)
        .where(EnforcementCase.status == "open")
        .order_by(EnforcementCase.risk_score.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [await _to_response(db, r) for r in rows]
    return EnforcementListResponse(items=items, total=len(items), page=1, per_page=limit)


async def _to_response(db: AsyncSession, enforcement_case: EnforcementCase) -> EnforcementCaseResponse:
    product_name = None
    company_name = None
    if enforcement_case.product_id:
        p = (await db.execute(
            select(Product).where(Product.id == enforcement_case.product_id)
        )).scalar_one_or_none()
        if p:
            product_name = p.name
    if enforcement_case.company_id:
        c = (await db.execute(
            select(Company).where(Company.id == enforcement_case.company_id)
        )).scalar_one_or_none()
        if c:
            company_name = c.name
    return EnforcementCaseResponse(
        id=enforcement_case.id,
        cluster_key=enforcement_case.cluster_key,
        product_name=product_name,
        company_name=company_name,
        scan_location_state=enforcement_case.scan_location_state,
        scan_location_lga=enforcement_case.scan_location_lga,
        market_name=enforcement_case.market_name,
        center_latitude=enforcement_case.center_latitude,
        center_longitude=enforcement_case.center_longitude,
        fake_scan_count=enforcement_case.fake_scan_count,
        suspicious_scan_count=enforcement_case.suspicious_scan_count,
        total_scan_count=enforcement_case.total_scan_count,
        risk_score=enforcement_case.risk_score,
        status=enforcement_case.status,
        assigned_officer_id=enforcement_case.assigned_officer_id,
        nafdac_case_ref=enforcement_case.nafdac_case_ref,
        evidence_package=enforcement_case.evidence_package,
        created_at=enforcement_case.created_at,
        updated_at=enforcement_case.updated_at,
    )
