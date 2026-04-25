from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class EnforcementCaseResponse(BaseModel):
    id: UUID
    cluster_key: str
    product_name: str | None
    company_name: str | None
    scan_location_state: str | None
    scan_location_lga: str | None
    market_name: str | None
    center_latitude: float | None
    center_longitude: float | None
    fake_scan_count: int
    suspicious_scan_count: int
    total_scan_count: int
    risk_score: float
    status: str
    assigned_officer_id: UUID | None
    nafdac_case_ref: str | None
    evidence_package: dict | None
    created_at: datetime
    updated_at: datetime


class EnforcementListResponse(BaseModel):
    items: list[EnforcementCaseResponse]
    total: int
    page: int
    per_page: int


class CaseUpdateRequest(BaseModel):
    status: Literal["open", "assigned", "raid_completed", "prosecuted", "closed"] | None = None
    assigned_officer_id: UUID | None = None
    nafdac_case_ref: str | None = None
