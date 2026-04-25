"""
TenantContext — derives the caller's tier and company_id from the verified JWT.
All admin endpoints depend on this; it is the single enforcement point for multi-tenancy.
"""
from uuid import UUID
from fastapi import Depends, HTTPException, status
from backend.dependencies import get_current_user
from backend.models.user import User

SUPER_ADMIN = "super_admin"
NAFDAC_ROLES = {"nafdac_officer", "nafdac_admin"}
COMPANY_ROLE = "company_admin"


class TenantContext:
    def __init__(self, user: User):
        self.user_id: UUID = user.id
        self.role: str = user.role
        self.company_id: UUID | None = user.company_id
        self.is_super: bool = user.role == SUPER_ADMIN
        self.is_nafdac: bool = user.role in NAFDAC_ROLES
        self.is_company: bool = user.role == COMPANY_ROLE

    # ------------------------------------------------------------------ #
    #  Query filters                                                        #
    # ------------------------------------------------------------------ #

    def apply_scan_filter(self, query):
        """Apply company_id filter to a scan query. No-op for super_admin and NAFDAC."""
        from backend.models.scan import Scan
        if self.is_company:
            return query.filter(Scan.company_id == self.company_id)
        return query

    def apply_report_filter(self, query):
        """Company admin sees only their own reports."""
        from backend.admin.models import AdminReport
        if self.is_company:
            return query.filter(AdminReport.company_id == self.company_id)
        return query

    def apply_enforcement_filter(self, query):
        """Company admin sees only their own enforcement cases."""
        from backend.admin.models import EnforcementCase
        if self.is_company:
            return query.filter(EnforcementCase.company_id == self.company_id)
        return query

    def apply_company_filter(self, query, company_id_col):
        """Generic company_id filter — supply the mapped column."""
        if self.is_company:
            return query.filter(company_id_col == self.company_id)
        return query

    # ------------------------------------------------------------------ #
    #  Ownership / role checks                                             #
    # ------------------------------------------------------------------ #

    def assert_report_owner(self, report) -> None:
        if self.is_company and str(report.company_id) != str(self.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Report does not belong to your company.",
            )

    def assert_not_nafdac(self) -> None:
        """Use on user-management and billing endpoints."""
        if self.is_nafdac:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="NAFDAC accounts cannot access this endpoint.",
            )

    def assert_admin_or_nafdac(self) -> None:
        """Blocks company_admin from enforcement endpoints."""
        if self.is_company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company accounts cannot access enforcement data.",
            )


async def get_tenant_ctx(
    current_user: User = Depends(get_current_user),
) -> TenantContext:
    """FastAPI dependency — inject as: ctx: TenantContext = Depends(get_tenant_ctx)"""
    allowed = {SUPER_ADMIN, COMPANY_ROLE} | NAFDAC_ROLES
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for admin access.",
        )
    return TenantContext(current_user)


def require_super_admin(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    if not ctx.is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required.",
        )
    return ctx


def require_nafdac_or_super(ctx: TenantContext = Depends(get_tenant_ctx)) -> TenantContext:
    ctx.assert_admin_or_nafdac()
    return ctx
