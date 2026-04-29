"""
NAFDAC access request CRUD and state machine transitions.

State machine:
  NAFDAC  → create (PENDING)
  NAFDAC  → withdraw / delete (PENDING only)
  SUPER   → approve PENDING → APPROVED  (sets approved_at, optional expires_at)
  SUPER   → reject  PENDING → REJECTED  (requires review_notes)
  SUPER   → revoke  APPROVED → REVOKED  (sets revoked_at)
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.models import NafdacAccessRequest
from backend.admin.schemas.access_requests import (
    AccessRequestCreate,
    AccessRequestListResponse,
    AccessRequestResponse,
    AccessRequestReview,
)
from backend.admin.dependencies import TenantContext


async def create_request(
    db: AsyncSession,
    ctx: TenantContext,
    payload: AccessRequestCreate,
) -> AccessRequestResponse:
    if not ctx.is_nafdac:
        raise HTTPException(403, "Only NAFDAC accounts can submit access requests.")
    if not ctx.jurisdiction:
        raise HTTPException(400, "Your account has no jurisdiction state configured. Contact a super admin.")

    req = NafdacAccessRequest(
        requested_by_id=ctx.user_id,
        jurisdiction=ctx.jurisdiction,
        breakdown_type=payload.breakdown_type,
        justification=payload.justification,
        filter_category=payload.filter_category,
        filter_date_from=payload.filter_date_from,
        filter_date_to=payload.filter_date_to,
    )
    db.add(req)
    try:
        await db.commit()
        await db.refresh(req)
    except Exception:
        await db.rollback()
        # The partial unique index uix_nafdac_access_one_active fires here
        raise HTTPException(409, "An active (pending or approved) request for this breakdown type already exists.")

    return AccessRequestResponse.model_validate(req)


async def list_own_requests(
    db: AsyncSession,
    ctx: TenantContext,
    status_filter: str | None = None,
) -> AccessRequestListResponse:
    stmt = (
        select(NafdacAccessRequest)
        .where(NafdacAccessRequest.requested_by_id == ctx.user_id)
    )
    if status_filter:
        stmt = stmt.where(NafdacAccessRequest.status == status_filter)
    stmt = stmt.order_by(NafdacAccessRequest.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    return AccessRequestListResponse(
        items=[AccessRequestResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


async def withdraw_request(
    db: AsyncSession,
    ctx: TenantContext,
    request_id: UUID,
) -> None:
    req = await _get_own_pending(db, ctx, request_id)
    await db.delete(req)
    await db.commit()


async def list_all_requests(
    db: AsyncSession,
    ctx: TenantContext,
    status_filter: str | None = "pending",
    page: int = 1,
    per_page: int = 20,
) -> AccessRequestListResponse:
    if not ctx.is_super:
        raise HTTPException(403, "Super admin access required.")

    count_stmt = select(func.count()).select_from(NafdacAccessRequest)
    data_stmt  = select(NafdacAccessRequest).order_by(NafdacAccessRequest.created_at.desc())

    if status_filter:
        count_stmt = count_stmt.where(NafdacAccessRequest.status == status_filter)
        data_stmt  = data_stmt.where(NafdacAccessRequest.status == status_filter)

    total = (await db.execute(count_stmt)).scalar_one()
    rows  = (await db.execute(data_stmt.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    return AccessRequestListResponse(
        items=[AccessRequestResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
    )


async def approve_request(
    db: AsyncSession,
    ctx: TenantContext,
    request_id: UUID,
    payload: AccessRequestReview,
) -> AccessRequestResponse:
    if not ctx.is_super:
        raise HTTPException(403, "Super admin access required.")
    req = await _get_by_id(db, request_id)
    if req.status != "pending":
        raise HTTPException(400, f"Cannot approve a '{req.status}' request.")

    now = datetime.now(timezone.utc)
    req.status       = "approved"
    req.reviewed_by_id = ctx.user_id
    req.review_notes = payload.review_notes
    req.approved_at  = now
    req.expires_at   = payload.expires_at
    req.updated_at   = now

    await db.commit()
    await db.refresh(req)
    return AccessRequestResponse.model_validate(req)


async def reject_request(
    db: AsyncSession,
    ctx: TenantContext,
    request_id: UUID,
    payload: AccessRequestReview,
) -> AccessRequestResponse:
    if not ctx.is_super:
        raise HTTPException(403, "Super admin access required.")
    req = await _get_by_id(db, request_id)
    if req.status != "pending":
        raise HTTPException(400, f"Cannot reject a '{req.status}' request.")
    if not payload.review_notes:
        raise HTTPException(400, "review_notes is required when rejecting a request.")

    now = datetime.now(timezone.utc)
    req.status         = "rejected"
    req.reviewed_by_id = ctx.user_id
    req.review_notes   = payload.review_notes
    req.updated_at     = now

    await db.commit()
    await db.refresh(req)
    return AccessRequestResponse.model_validate(req)


async def revoke_request(
    db: AsyncSession,
    ctx: TenantContext,
    request_id: UUID,
    payload: AccessRequestReview,
) -> AccessRequestResponse:
    if not ctx.is_super:
        raise HTTPException(403, "Super admin access required.")
    req = await _get_by_id(db, request_id)
    if req.status != "approved":
        raise HTTPException(400, f"Cannot revoke a '{req.status}' request.")

    now = datetime.now(timezone.utc)
    req.status         = "revoked"
    req.reviewed_by_id = ctx.user_id
    req.review_notes   = payload.review_notes
    req.revoked_at     = now
    req.updated_at     = now

    await db.commit()
    await db.refresh(req)
    return AccessRequestResponse.model_validate(req)


# ── Private helpers ────────────────────────────────────────────────────────────

async def _get_by_id(db: AsyncSession, request_id: UUID) -> NafdacAccessRequest:
    req = await db.get(NafdacAccessRequest, request_id)
    if not req:
        raise HTTPException(404, "Access request not found.")
    return req


async def _get_own_pending(
    db: AsyncSession, ctx: TenantContext, request_id: UUID
) -> NafdacAccessRequest:
    req = await _get_by_id(db, request_id)
    if str(req.requested_by_id) != str(ctx.user_id):
        raise HTTPException(403, "This request does not belong to you.")
    if req.status != "pending":
        raise HTTPException(400, "Only pending requests can be withdrawn.")
    return req
