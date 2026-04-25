"""Heatmap geographic aggregation service."""
from __future__ import annotations
from typing import Literal
from uuid import UUID

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.dependencies import TenantContext
from backend.admin.schemas.heatmap import HeatmapFilters, HeatmapPoint, HeatmapResponse
from backend.models.scan import Scan
from backend.models.company import Company


def _risk_level(fake_proportion: float) -> Literal["critical", "high", "medium", "low"]:
    if fake_proportion > 30:
        return "critical"
    elif fake_proportion > 15:
        return "high"
    elif fake_proportion > 5:
        return "medium"
    return "low"


async def get_heatmap(
    db: AsyncSession,
    ctx: TenantContext,
    filters: HeatmapFilters,
) -> HeatmapResponse:
    """
    Returns heatmap data points aggregated by state / LGA / market.

    Tenant scoping:
    - company_admin  → WHERE scans.company_id = ctx.company_id
    - nafdac / super → no company filter

    NDPR: company_admin coordinates rounded to 2 d.p. (LGA centroid precision).
    """
    total_col = func.count().label("total_scans")
    fake_col = func.sum(case((Scan.status == "fake", 1), else_=0)).label("fake_count")
    susp_col = func.sum(case((Scan.status == "suspicious", 1), else_=0)).label("suspicious_count")
    lat_col = func.avg(Scan.latitude).label("center_latitude")
    lng_col = func.avg(Scan.longitude).label("center_longitude")

    stmt = (
        select(
            Scan.scan_location_state.label("state"),
            Scan.scan_location_lga.label("lga"),
            Scan.market_name,
            Scan.company_id,
            lat_col,
            lng_col,
            total_col,
            fake_col,
            susp_col,
        )
        .where(Scan.scan_location_state.isnot(None))
    )

    stmt = ctx.apply_scan_filter(stmt)

    if filters.date_from:
        stmt = stmt.where(Scan.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Scan.created_at <= filters.date_to)
    if filters.state:
        stmt = stmt.where(Scan.scan_location_state == filters.state)
    if filters.lga:
        stmt = stmt.where(Scan.scan_location_lga == filters.lga)
    if filters.subcategory_id:
        from backend.models.product import Product
        stmt = stmt.join(Product, Scan.product_id == Product.id, isouter=True)
        stmt = stmt.where(Product.category_id == filters.subcategory_id)

    stmt = stmt.group_by(
        Scan.scan_location_state,
        Scan.scan_location_lga,
        Scan.market_name,
        Scan.company_id,
    ).order_by(fake_col.desc())

    rows = (await db.execute(stmt)).mappings().all()

    # Resolve company names in a single follow-up query
    company_ids = {r["company_id"] for r in rows if r["company_id"]}
    company_names: dict[UUID, str] = {}
    if company_ids:
        c_result = await db.execute(
            select(Company.id, Company.name).where(Company.id.in_(company_ids))
        )
        company_names = {row.id: row.name for row in c_result}

    points: list[HeatmapPoint] = []
    for row in rows:
        total = row["total_scans"] or 1
        fake = row["fake_count"] or 0
        susp = row["suspicious_count"] or 0
        fake_prop = round(fake / total * 100, 2)
        combined = round((fake + susp) / total * 100, 2)

        raw_lat = float(row["center_latitude"]) if row["center_latitude"] else None
        raw_lng = float(row["center_longitude"]) if row["center_longitude"] else None

        # NDPR: truncate coordinates for company_admin callers
        if ctx.is_company:
            lat = round(raw_lat, 2) if raw_lat is not None else None
            lng = round(raw_lng, 2) if raw_lng is not None else None
        else:
            lat, lng = raw_lat, raw_lng

        company_id = row["company_id"]
        points.append(HeatmapPoint(
            state=row["state"],
            lga=row["lga"],
            market_name=row["market_name"],
            center_latitude=lat,
            center_longitude=lng,
            total_scans=row["total_scans"],
            fake_count=fake,
            suspicious_count=susp,
            fake_proportion=fake_prop,
            combined_risk_rate=combined,
            risk_level=_risk_level(fake_prop),
            company_id=company_id if not ctx.is_company else None,
            company_name=company_names.get(company_id) if not ctx.is_company else None,
            can_get_report=True,
        ))

    return HeatmapResponse(
        points=points,
        total_points=len(points),
        filters_applied=filters,
    )
