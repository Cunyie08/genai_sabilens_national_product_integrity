from __future__ import annotations
from uuid import UUID
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class OverviewMetricsResponse(BaseModel):
    period_start: date
    period_end: date
    total_scans: int
    total_scans_today: int
    total_scans_this_month: int
    total_scans_change_pct: float
    authentic_count: int
    suspicious_count: int
    fake_count: int
    authentic_rate_pct: float
    fake_rate_pct: float
    fake_rate_change_pct: float
    total_products_scanned: int
    top_fake_product_name: str | None
    top_fake_product_fake_count: int | None
    avg_confidence_score: float
    top_risk_state: str | None
    top_risk_lga: str | None
    open_alert_count: int
    critical_alert_count: int
    active_users_30d: int | None
    total_companies: int | None


class ProductVerdictBreakdown(BaseModel):
    product_id: UUID
    product_name: str
    nafdac_number: str | None
    total_scans: int
    authentic_count: int
    suspicious_count: int
    fake_count: int
    fake_pct: float
    top_fake_state: str | None
    top_fake_lga: str | None
    last_scan_at: datetime | None


class ProductVerdictListResponse(BaseModel):
    items: list[ProductVerdictBreakdown]
    total: int
    page: int
    per_page: int


class TrendPoint(BaseModel):
    period: str
    authentic_count: int
    suspicious_count: int
    fake_count: int
    total_scans: int
    fake_rate_pct: float


class TrendResponse(BaseModel):
    granularity: Literal["daily", "weekly", "monthly"]
    points: list[TrendPoint]


class TopMarketItem(BaseModel):
    state: str
    lga: str | None
    market_name: str | None
    total_scans: int
    fake_count: int
    fake_pct: float
    risk_level: Literal["critical", "high", "medium", "low"]


class TopMarketsResponse(BaseModel):
    items: list[TopMarketItem]


class StateBreakdownItem(BaseModel):
    state: str
    total_scans: int
    fake_count: int
    fake_pct: float
    risk_level: Literal["critical", "high", "medium", "low"]


class StateBreakdownResponse(BaseModel):
    items: list[StateBreakdownItem]
