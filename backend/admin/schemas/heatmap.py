from __future__ import annotations
from uuid import UUID
from datetime import date
from typing import Literal
from pydantic import BaseModel


class HeatmapFilters(BaseModel):
    state: str | None = None
    lga: str | None = None
    subcategory_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class HeatmapPoint(BaseModel):
    state: str
    lga: str | None
    market_name: str | None
    center_latitude: float | None
    center_longitude: float | None
    total_scans: int
    fake_count: int
    suspicious_count: int
    fake_proportion: float
    combined_risk_rate: float
    risk_level: Literal["critical", "high", "medium", "low"]
    company_id: UUID | None
    company_name: str | None
    can_get_report: bool = True


class HeatmapResponse(BaseModel):
    points: list[HeatmapPoint]
    total_points: int
    filters_applied: HeatmapFilters
