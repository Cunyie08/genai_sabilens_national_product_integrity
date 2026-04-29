"""
TenantContext — single enforcement point for all multi-tenancy rules.

Rules applied here and nowhere else:
  COMPANY_ADMIN  → queries scoped to own company_id (JWT-bound, never request-body)
  NAFDAC roles   → queries geofenced to user.state (jurisdiction); brand/quantity
                   data gated behind an approved NafdacAccessRequest
  SUPER_ADMIN    → no filters applied; full platform access
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User

SUPER_ADMIN  = "super_admin"
NAFDAC_ROLES = {"nafdac_officer", "nafdac_admin"}
COMPANY_ROLE = "company_admin"


class TenantContext:
    def __init__(self, user: User, approved_breakdown_types: set[str]):
        self.user_id:    UUID       = user.id
        self.role:       str        = user.role
        self.company_id: UUID | None = user.company_id
        self.jurisdiction: str | None = user.state   # user.state IS the NAFDAC jurisdiction
        self.is_super:   bool = user.role == SUPER_ADMIN
        self.is_nafdac:  bool = user.role in NAFDAC_ROLES
        self.is_company: bool = user.role == COMPANY_ROLE
        self._approved:  set[str] = approved_breakdown_types

    # ── Granular access ───────────────────────────────────────────────────────

    def has_granular_access(self, breakdown_type: str) -> bool:
        """True if NAFDAC admin has a live approved request for this type."""
        if self.is_super:
            return True
        return breakdown_type in self._approved

    # ── Query filters ─────────────────────────────────────────────────────────

    def apply_scan_filter(self, query):
        """Scope a Scan query to this caller's data boundary."""
        from backend.models.scan import Scan
        if self.is_company:
            return query.filter(Scan.company_id == self.company_id)
        if self.is_nafdac:
            if not self.jurisdiction:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "NAFDAC account has no jurisdiction state configured.",
                )
            return query.filter(Scan.scan_location_state == self.jurisdiction)
        return query  # super_admin: no filter

    def apply_enforcement_filter(self, query):
        from backend.admin.models import EnforcementCase
        if self.is_company:
            return query.filter(EnforcementCase.company_id == self.company_id)
        if self.is_nafdac:
            if not self.jurisdiction:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "No jurisdiction configured.")
            return query.filter(EnforcementCase.scan_location_state == self.jurisdiction)
        return query

    def apply_report_filter(self, query):
        from backend.admin.models import AdminReport
        if self.is_company:
            return query.filter(AdminReport.company_id == self.company_id)
        if self.is_nafdac:
            return query.filter(AdminReport.filter_state == self.jurisdiction)
        return query

    def apply_company_filter(self, query, company_id_col):
        """Generic company_id filter — supply the mapped column."""
        if self.is_company:
            return query.filter(company_id_col == self.company_id)
        return query

    # ── Granular access gates ─────────────────────────────────────────────────

    def assert_can_see_brand_data(self) -> None:
        if self.is_nafdac and not self.has_granular_access("brand_breakdown"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Brand-level data requires an approved Further Breakdown request.",
            )

    def assert_can_see_quantity_data(self) -> None:
        if self.is_nafdac and not self.has_granular_access("quantity_breakdown"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Exact quantity data requires an approved Further Breakdown request.",
            )

    # ── Ownership / role checks ───────────────────────────────────────────────

    def assert_report_owner(self, report) -> None:
        if self.is_company and str(report.company_id) != str(self.company_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Report does not belong to your company.")

    def assert_not_nafdac(self) -> None:
        """Block NAFDAC accounts from user-management and billing endpoints."""
        if self.is_nafdac:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "NAFDAC accounts cannot access this endpoint.")

    def assert_admin_or_nafdac(self) -> None:
        """Block company_admin from enforcement endpoints."""
        if self.is_company:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Company accounts cannot access enforcement data.")


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_tenant_ctx(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Inject as: ctx: TenantContext = Depends(get_tenant_ctx)"""
    allowed = {SUPER_ADMIN, COMPANY_ROLE} | NAFDAC_ROLES
    if current_user.role not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for admin access.")

    approved: set[str] = set()
    if current_user.role in NAFDAC_ROLES:
        from backend.admin.models import NafdacAccessRequest
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(NafdacAccessRequest.breakdown_type).where(
                NafdacAccessRequest.requested_by_id == current_user.id,
                NafdacAccessRequest.status == "approved",
                or_(
                    NafdacAccessRequest.expires_at.is_(None),
                    NafdacAccessRequest.expires_at > now,
                ),
            )
        )
        approved = {row[0] for row in result.all()}

    return TenantContext(current_user, approved)


def require_super_admin(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    if not ctx.is_super:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required.")
    return ctx


def require_nafdac(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    if not ctx.is_nafdac:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NAFDAC account required.")
    return ctx


def require_company_admin(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    if not ctx.is_company:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company admin account required.")
    return ctx


def require_nafdac_or_super(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    ctx.assert_admin_or_nafdac()
    return ctx
