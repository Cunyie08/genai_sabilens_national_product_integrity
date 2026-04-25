"""Overview KPIs, trend, product breakdown, and market summaries."""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select, func, case, text, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.dependencies import TenantContext
from backend.admin.schemas.metrics import (
    OverviewMetricsResponse,
    ProductVerdictBreakdown,
    ProductVerdictListResponse,
    TrendPoint,
    TrendResponse,
    TopMarketItem,
    TopMarketsResponse,
    StateBreakdownItem,
    StateBreakdownResponse,
)
from backend.models.scan import Scan
from backend.models.product import Product
from backend.models.alert import Alert
from backend.models.company import Company
from backend.models.user import User


def _risk_level(fake_pct: float) -> str:
    if fake_pct > 30:
        return "critical"
    elif fake_pct > 15:
        return "high"
    elif fake_pct > 5:
        return "medium"
    return "low"


async def get_overview(
    db: AsyncSession,
    ctx: TenantContext,
    period_days: int = 30,
) -> OverviewMetricsResponse:
    now = datetime.now(timezone.utc)
    period_end = now.date()
    period_start = (now - timedelta(days=period_days)).date()
    prev_start = (now - timedelta(days=period_days * 2)).date()

    fake_expr = func.sum(case((Scan.status == "fake", 1), else_=0))
    susp_expr = func.sum(case((Scan.status == "suspicious", 1), else_=0))
    auth_expr = func.sum(case((Scan.status == "authentic", 1), else_=0))

    # Current period counts
    cur_stmt = (
        select(
            func.count().label("total"),
            fake_expr.label("fake"),
            susp_expr.label("susp"),
            auth_expr.label("auth"),
            func.avg(Scan.confidence_score).label("avg_conf"),
            func.count(distinct(Scan.product_id)).label("products"),
        )
        .where(Scan.created_at >= period_start)
        .where(Scan.created_at <= period_end)
    )
    cur_stmt = ctx.apply_scan_filter(cur_stmt)
    cur = (await db.execute(cur_stmt)).mappings().one()

    # Previous period total (for change %)
    prev_stmt = (
        select(func.count().label("total"))
        .where(Scan.created_at >= prev_start)
        .where(Scan.created_at < period_start)
    )
    prev_stmt = ctx.apply_scan_filter(prev_stmt)
    prev_total = (await db.execute(prev_stmt)).scalar_one() or 0

    total = cur["total"] or 0
    fake = cur["fake"] or 0
    susp = cur["susp"] or 0
    auth = cur["auth"] or 0

    def _change_pct(curr: int, prev: int) -> float:
        if prev == 0:
            return 0.0
        return round((curr - prev) / prev * 100, 2)

    # Previous period fake rate
    prev_fake_stmt = (
        select(
            func.count().label("total"),
            func.sum(case((Scan.status == "fake", 1), else_=0)).label("fake"),
        )
        .where(Scan.created_at >= prev_start)
        .where(Scan.created_at < period_start)
    )
    prev_fake_stmt = ctx.apply_scan_filter(prev_fake_stmt)
    prev_f = (await db.execute(prev_fake_stmt)).mappings().one()
    prev_fake_rate = round((prev_f["fake"] or 0) / max(prev_f["total"] or 1, 1) * 100, 2)
    cur_fake_rate = round(fake / max(total, 1) * 100, 2)

    # Today's scans
    today_stmt = (
        select(func.count())
        .where(func.date(Scan.created_at) == now.date())
    )
    today_stmt = ctx.apply_scan_filter(today_stmt)
    scans_today = (await db.execute(today_stmt)).scalar_one() or 0

    # This month's scans
    month_start = now.replace(day=1).date()
    month_stmt = (
        select(func.count())
        .where(Scan.created_at >= month_start)
    )
    month_stmt = ctx.apply_scan_filter(month_stmt)
    scans_month = (await db.execute(month_stmt)).scalar_one() or 0

    # Top fake product
    top_prod_stmt = (
        select(
            Product.name.label("name"),
            func.sum(case((Scan.status == "fake", 1), else_=0)).label("fc"),
        )
        .join(Product, Scan.product_id == Product.id, isouter=True)
        .where(Scan.created_at >= period_start)
        .where(Product.id.isnot(None))
        .group_by(Product.id, Product.name)
        .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
        .limit(1)
    )
    top_prod_stmt = ctx.apply_scan_filter(top_prod_stmt)
    top_prod_row = (await db.execute(top_prod_stmt)).mappings().first()
    top_fake_product_name = top_prod_row["name"] if top_prod_row else None
    top_fake_product_fake_count = int(top_prod_row["fc"]) if top_prod_row else None

    # Top risk state
    top_state_stmt = (
        select(
            Scan.scan_location_state.label("state"),
            func.sum(case((Scan.status == "fake", 1), else_=0)).label("fc"),
        )
        .where(Scan.created_at >= period_start)
        .where(Scan.scan_location_state.isnot(None))
        .group_by(Scan.scan_location_state)
        .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
        .limit(1)
    )
    top_state_stmt = ctx.apply_scan_filter(top_state_stmt)
    top_state_row = (await db.execute(top_state_stmt)).mappings().first()
    top_risk_state = top_state_row["state"] if top_state_row else None

    # Top risk LGA
    top_lga_stmt = (
        select(
            Scan.scan_location_lga.label("lga"),
            func.sum(case((Scan.status == "fake", 1), else_=0)).label("fc"),
        )
        .where(Scan.created_at >= period_start)
        .where(Scan.scan_location_lga.isnot(None))
        .group_by(Scan.scan_location_lga)
        .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
        .limit(1)
    )
    top_lga_stmt = ctx.apply_scan_filter(top_lga_stmt)
    top_lga_row = (await db.execute(top_lga_stmt)).mappings().first()
    top_risk_lga = top_lga_row["lga"] if top_lga_row else None

    # Alert counts (company-scoped where applicable)
    alert_base = select(func.count()).select_from(Alert)
    if ctx.is_company:
        alert_base = alert_base.where(Alert.company_id == ctx.company_id)

    open_alerts = (await db.execute(
        alert_base.where(Alert.is_acknowledged == False)
    )).scalar_one() or 0

    critical_alerts = (await db.execute(
        alert_base.where(Alert.severity == "critical").where(Alert.is_acknowledged == False)
    )).scalar_one() or 0

    # Super admin only fields
    active_users_30d: int | None = None
    total_companies: int | None = None
    if ctx.is_super:
        active_users_30d = (await db.execute(
            select(func.count(distinct(Scan.user_id)))
            .where(Scan.created_at >= period_start)
        )).scalar_one() or 0

        total_companies = (await db.execute(
            select(func.count()).select_from(Company)
        )).scalar_one() or 0

    return OverviewMetricsResponse(
        period_start=period_start,
        period_end=period_end,
        total_scans=total,
        total_scans_today=scans_today,
        total_scans_this_month=scans_month,
        total_scans_change_pct=_change_pct(total, prev_total),
        authentic_count=auth,
        suspicious_count=susp,
        fake_count=fake,
        authentic_rate_pct=round(auth / max(total, 1) * 100, 2),
        fake_rate_pct=cur_fake_rate,
        fake_rate_change_pct=_change_pct(int(cur_fake_rate * 100), int(prev_fake_rate * 100)),
        total_products_scanned=cur["products"] or 0,
        top_fake_product_name=top_fake_product_name,
        top_fake_product_fake_count=top_fake_product_fake_count,
        avg_confidence_score=round(float(cur["avg_conf"] or 0), 4),
        top_risk_state=top_risk_state,
        top_risk_lga=top_risk_lga,
        open_alert_count=open_alerts,
        critical_alert_count=critical_alerts,
        active_users_30d=active_users_30d,
        total_companies=total_companies,
    )


async def get_trend(
    db: AsyncSession,
    ctx: TenantContext,
    granularity: Literal["daily", "weekly", "monthly"],
    date_from: date,
    date_to: date,
) -> TrendResponse:
    trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    trunc = trunc_map[granularity]

    bucket = func.date_trunc(trunc, Scan.created_at).label("period")
    stmt = (
        select(
            bucket,
            Scan.status,
            func.count().label("cnt"),
        )
        .where(Scan.created_at >= date_from)
        .where(Scan.created_at <= date_to)
        .group_by(bucket, Scan.status)
        .order_by(bucket)
    )
    stmt = ctx.apply_scan_filter(stmt)

    rows = (await db.execute(stmt)).mappings().all()

    # Pivot: group by period
    buckets: dict[str, dict] = {}
    for row in rows:
        key = str(row["period"])[:10]
        if key not in buckets:
            buckets[key] = {"authentic": 0, "suspicious": 0, "fake": 0}
        if row["status"] in buckets[key]:
            buckets[key][row["status"]] += row["cnt"]

    points = []
    for period_key in sorted(buckets):
        b = buckets[period_key]
        total = b["authentic"] + b["suspicious"] + b["fake"]
        points.append(TrendPoint(
            period=period_key,
            authentic_count=b["authentic"],
            suspicious_count=b["suspicious"],
            fake_count=b["fake"],
            total_scans=total,
            fake_rate_pct=round(b["fake"] / max(total, 1) * 100, 2),
        ))

    return TrendResponse(granularity=granularity, points=points)


async def get_product_breakdown(
    db: AsyncSession,
    ctx: TenantContext,
    page: int = 1,
    per_page: int = 20,
) -> ProductVerdictListResponse:
    fake_expr = func.sum(case((Scan.status == "fake", 1), else_=0))
    susp_expr = func.sum(case((Scan.status == "suspicious", 1), else_=0))
    auth_expr = func.sum(case((Scan.status == "authentic", 1), else_=0))

    stmt = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.nafdac_number,
            func.count(Scan.id).label("total_scans"),
            auth_expr.label("authentic_count"),
            susp_expr.label("suspicious_count"),
            fake_expr.label("fake_count"),
            func.max(Scan.created_at).label("last_scan_at"),
        )
        .join(Product, Scan.product_id == Product.id)
        .group_by(Product.id, Product.name, Product.nafdac_number)
        .order_by(fake_expr.desc())
    )
    stmt = ctx.apply_scan_filter(stmt)

    count_stmt = (
        select(func.count(distinct(Scan.product_id)))
        .join(Product, Scan.product_id == Product.id)
    )
    count_stmt = ctx.apply_scan_filter(count_stmt)

    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).mappings().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0

    # Top fake state per product (batch query)
    product_ids = [r["product_id"] for r in rows]
    top_state_map: dict[UUID, str] = {}
    top_lga_map: dict[UUID, str] = {}

    if product_ids:
        state_stmt = (
            select(
                Scan.product_id,
                Scan.scan_location_state,
                func.sum(case((Scan.status == "fake", 1), else_=0)).label("fc"),
            )
            .where(Scan.product_id.in_(product_ids))
            .where(Scan.scan_location_state.isnot(None))
            .group_by(Scan.product_id, Scan.scan_location_state)
            .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
        )
        state_rows = (await db.execute(state_stmt)).mappings().all()
        seen_state: set[UUID] = set()
        for sr in state_rows:
            pid = sr["product_id"]
            if pid not in seen_state:
                top_state_map[pid] = sr["scan_location_state"]
                seen_state.add(pid)

        lga_stmt = (
            select(
                Scan.product_id,
                Scan.scan_location_lga,
                func.sum(case((Scan.status == "fake", 1), else_=0)).label("fc"),
            )
            .where(Scan.product_id.in_(product_ids))
            .where(Scan.scan_location_lga.isnot(None))
            .group_by(Scan.product_id, Scan.scan_location_lga)
            .order_by(func.sum(case((Scan.status == "fake", 1), else_=0)).desc())
        )
        lga_rows = (await db.execute(lga_stmt)).mappings().all()
        seen_lga: set[UUID] = set()
        for lr in lga_rows:
            pid = lr["product_id"]
            if pid not in seen_lga:
                top_lga_map[pid] = lr["scan_location_lga"]
                seen_lga.add(pid)

    items = []
    for row in rows:
        t = row["total_scans"] or 1
        items.append(ProductVerdictBreakdown(
            product_id=row["product_id"],
            product_name=row["product_name"],
            nafdac_number=row["nafdac_number"],
            total_scans=row["total_scans"],
            authentic_count=row["authentic_count"] or 0,
            suspicious_count=row["suspicious_count"] or 0,
            fake_count=row["fake_count"] or 0,
            fake_pct=round((row["fake_count"] or 0) / t * 100, 2),
            top_fake_state=top_state_map.get(row["product_id"]),
            top_fake_lga=top_lga_map.get(row["product_id"]),
            last_scan_at=row["last_scan_at"],
        ))

    return ProductVerdictListResponse(items=items, total=total, page=page, per_page=per_page)


async def get_top_markets(
    db: AsyncSession,
    ctx: TenantContext,
    limit: int = 20,
) -> TopMarketsResponse:
    fake_expr = func.sum(case((Scan.status == "fake", 1), else_=0))

    stmt = (
        select(
            Scan.scan_location_state.label("state"),
            Scan.scan_location_lga.label("lga"),
            Scan.market_name,
            func.count().label("total_scans"),
            fake_expr.label("fake_count"),
        )
        .where(Scan.scan_location_state.isnot(None))
        .group_by(Scan.scan_location_state, Scan.scan_location_lga, Scan.market_name)
        .order_by(fake_expr.desc())
        .limit(limit)
    )
    stmt = ctx.apply_scan_filter(stmt)

    rows = (await db.execute(stmt)).mappings().all()
    items = []
    for row in rows:
        t = row["total_scans"] or 1
        fake = row["fake_count"] or 0
        fake_pct = round(fake / t * 100, 2)
        items.append(TopMarketItem(
            state=row["state"],
            lga=row["lga"],
            market_name=row["market_name"],
            total_scans=row["total_scans"],
            fake_count=fake,
            fake_pct=fake_pct,
            risk_level=_risk_level(fake_pct),
        ))

    return TopMarketsResponse(items=items)


async def get_state_breakdown(
    db: AsyncSession,
    ctx: TenantContext,
) -> StateBreakdownResponse:
    fake_expr = func.sum(case((Scan.status == "fake", 1), else_=0))

    stmt = (
        select(
            Scan.scan_location_state.label("state"),
            func.count().label("total_scans"),
            fake_expr.label("fake_count"),
        )
        .where(Scan.scan_location_state.isnot(None))
        .group_by(Scan.scan_location_state)
        .order_by(fake_expr.desc())
    )
    stmt = ctx.apply_scan_filter(stmt)

    rows = (await db.execute(stmt)).mappings().all()
    items = []
    for row in rows:
        t = row["total_scans"] or 1
        fake = row["fake_count"] or 0
        fake_pct = round(fake / t * 100, 2)
        items.append(StateBreakdownItem(
            state=row["state"],
            total_scans=row["total_scans"],
            fake_count=fake,
            fake_pct=fake_pct,
            risk_level=_risk_level(fake_pct),
        ))

    return StateBreakdownResponse(items=items)
