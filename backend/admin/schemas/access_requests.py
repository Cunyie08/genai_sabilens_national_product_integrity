from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, field_validator


class AccessRequestCreate(BaseModel):
    breakdown_type: Literal["brand_breakdown", "quantity_breakdown", "company_breakdown"]
    justification:   str
    filter_category:  str | None  = None
    filter_date_from: date | None = None
    filter_date_to:   date | None = None

    @field_validator("justification")
    @classmethod
    def justification_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("justification cannot be blank")
        return v.strip()


class AccessRequestReview(BaseModel):
    """Body for approve / reject / revoke actions (all super admin only)."""
    review_notes: str | None  = None
    expires_at:   datetime | None = None   # approve only — sets access TTL


class AccessRequestResponse(BaseModel):
    id:               UUID
    requested_by_id:  UUID
    jurisdiction:     str
    breakdown_type:   str
    justification:    str
    filter_category:  str | None
    filter_date_from: date | None
    filter_date_to:   date | None
    status:           str
    reviewed_by_id:   UUID | None
    review_notes:     str | None
    approved_at:      datetime | None
    expires_at:       datetime | None
    revoked_at:       datetime | None
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class AccessRequestListResponse(BaseModel):
    items: list[AccessRequestResponse]
    total: int
    page:  int = 1
