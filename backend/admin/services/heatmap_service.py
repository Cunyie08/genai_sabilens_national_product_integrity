"""
Heatmap geographic aggregation service — role-adaptive GROUP BY.

GROUP BY level:
  Super Admin  + no ?state filter  → scan_location_state  (36 state rows)
  Super Admin  + ?state=X          → scan_location_lga WHERE state=X  (drill-down)
  NAFDAC Admin                     → scan_location_lga WHERE state=ctx.jurisdiction
  Company Admin                    → scan_location_lga WHERE company_id=ctx.company_id
"""
from __future__ import annotations
from typing import Literal

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.dependencies import TenantContext
from backend.admin.schemas.heatmap import HeatmapFilters, HeatmapFeature, HeatmapResponse
from backend.admin import nafdac_categories
from backend.models.scan import Scan


def _risk_level(fake_pct: float) -> Literal["critical", "high", "medium", "low"]:
    if fake_pct > 30: return "critical"
    if fake_pct > 15: return "high"
    if fake_pct > 5:  return "medium"
    return "low"


def _display_name(geo_id: str, level: str) -> str:
    return f"{geo_id} State" if level == "state" else f"{geo_id} LGA"


def _is_state_level(ctx: TenantContext, filters: HeatmapFilters) -> bool:
    """Super Admin with no state filter → aggregate by state. All others → by LGA."""
    return ctx.is_super and not filters.state


async def get_heatmap(
    db: AsyncSession,
    ctx: TenantContext,
    filters: HeatmapFilters,
) -> HeatmapResponse:
    state_level = _is_state_level(ctx, filters)
    group_col   = Scan.scan_location_state if state_level else Scan.scan_location_lga

    stmt = (
        select(
            group_col.label("geo_id"),
            func.avg(Scan.latitude).label("center_lat"),
            func.avg(Scan.longitude).label("center_lng"),
            func.count().label("total_scans"),
            func.sum(case((Scan.status == "fake",       1), else_=0)).label("fake_count"),
            func.sum(case((Scan.status == "suspicious", 1), else_=0)).label("suspicious_count"),
            func.sum(case((Scan.status == "authentic",  1), else_=0)).label("authentic_count"),
        )
        .where(group_col.isnot(None))
    )

    # ── RBAC / geofence (applied by TenantContext — never from request body) ──
    stmt = ctx.apply_scan_filter(stmt)

    # ── Optional request-level filters ───────────────────────────────────────
    if filters.state and ctx.is_super:          # Super Admin drill-down only
        stmt = stmt.where(Scan.scan_location_state == filters.state)
    if filters.lga:
        stmt = stmt.where(Scan.scan_location_lga == filters.lga)
    if filters.date_from:
        stmt = stmt.where(Scan.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Scan.created_at <= filters.date_to)
    if filters.subcategory:
        from backend.models.product import Product, ProductCategory
        cat_name = nafdac_categories.resolve_subcategory(filters.subcategory)
        stmt = (
            stmt
            .join(Product, Scan.product_id == Product.id, isouter=True)
            .join(ProductCategory, Product.category_id == ProductCategory.id, isouter=True)
            .where(ProductCategory.name == cat_name)
        )

    stmt = (
        stmt
        .group_by(group_col)
        .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
    )

    rows = (await db.execute(stmt)).mappings().all()

    aggregation_level: Literal["state", "lga"] = "state" if state_level else "lga"
    parent_geo: str | None = (
        filters.state         if (not state_level and filters.state and ctx.is_super)
        else ctx.jurisdiction if ctx.is_nafdac
        else None
    )

    features: list[HeatmapFeature] = []
    for row in rows:
        total = row["total_scans"] or 1
        fake  = row["fake_count"]  or 0
        susp  = row["suspicious_count"] or 0
        auth  = row["authentic_count"]  or 0
        fake_pct = round(fake / total * 100, 2)
        combined = round((fake + susp) / total * 100, 2)

        lat = float(row["center_lat"]) if row["center_lat"] else None
        lng = float(row["center_lng"]) if row["center_lng"] else None
        if ctx.is_company:              # NDPR: coarsen coordinates to ~LGA centroid precision
            lat = round(lat, 2) if lat is not None else None
            lng = round(lng, 2) if lng is not None else None

        features.append(HeatmapFeature(
            geo_id=row["geo_id"],
            display_name=_display_name(row["geo_id"], aggregation_level),
            center_lat=lat,
            center_lng=lng,
            total_scans=row["total_scans"],
            fake_count=fake,
            suspicious_count=susp,
            authentic_count=auth,
            fake_pct=fake_pct,
            combined_risk_rate=combined,
            risk_level=_risk_level(fake_pct),
            breakdown_locked=(
                ctx.is_nafdac
                and not ctx.has_granular_access("quantity_breakdown")
            ),
        ))

    return HeatmapResponse(
        aggregation_level=aggregation_level,
        parent_geo=parent_geo,
        features=features,
        filters_applied=filters,
        total_features=len(features),
    )
