from __future__ import annotations
from uuid import UUID
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class ReportTriggerRequest(BaseModel):
    report_type: Literal[
        "scan_analysis",
        "product_intelligence",
        "market_summary",
        "company_overview",
    ]
    filter_state: str | None = None
    filter_lga: str | None = None
    filter_subcategory_id: UUID | None = None
    filter_date_from: date | None = None
    filter_date_to: date | None = None


class ReportTriggerResponse(BaseModel):
    report_id: UUID
    company_id: UUID | None
    task_id: str
    status: Literal["queued", "processing"]
    message: str


class ReportStatusResponse(BaseModel):
    report_id: UUID
    report_type: str
    status: Literal["queued", "processing", "ready", "failed"]
    pdf_url: str | None
    pdf_expires_at: datetime | None
    report_json: dict | None
    generated_at: datetime | None
    error_message: str | None
    created_at: datetime


class ReportListItem(BaseModel):
    report_id: UUID
    report_type: str
    status: str
    generated_at: datetime | None
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total: int
    page: int
    per_page: int
