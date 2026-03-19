"""
NAFDAC Router — Barrister Femi
All /api/nafdac/* endpoints.
~65 route handlers across 12 endpoint groups.
"""

import csv
import os
import uuid as _uuid
from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, update, delete, func, and_, or_, desc, case, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend_femi.database import get_db
from backend_femi.dependencies import get_current_user, require_role
from backend_femi.config import settings
from backend_femi.models.user import User
from backend_femi.models.company import Company
from backend_femi.models.product import Product, ProductCategory
from backend_femi.models.scan import Scan
from backend_femi.models.report import Report, ReportEvidence
from backend_femi.models.alert import Alert, Notification, NotificationPreference
from backend_femi.models.analytics import (
    AnalyticsDaily, AnalyticsCategory, AnalyticsRegion,
    Hotspot, VendorLocation, NigerianState, AuditLog
)
from backend_femi.schemas.nafdac import (
    BootstrapOfficerCreate, OfficerCreate, OfficerUpdate, OfficerResponse,
    CompanyListResponse, CompanyDetailResponse, CompanyVerifyRequest,
    CompanyRejectRequest, CompanyStatsResponse,
    DashboardStatsResponse, DashboardRegionData, DashboardTrendData,
    LiveAlertResponse,
    AlertResponse, AlertAcknowledgeRequest, AlertResolveRequest,
    BulkAcknowledgeRequest, AlertStatsResponse,
    CaseResponse, CaseAssignRequest, CaseStatusUpdateRequest,
    VendorResponse, VendorBlacklistRequest, VendorInvestigateRequest, VendorStatsResponse,
    AnalyticsFilter, CategoryAnalyticsResponse, RegionAnalyticsResponse,
    TrendComparisonResponse, TimelineResponse, HotspotResponse, PredictionResponse,
    ExportRequest,
    RaidScheduleRequest, WarningNoticeRequest, SeizureLogRequest,
    BroadcastRequest, CompanyNotificationRequest, NotificationSettingsUpdate,
    RiskLevelConfig, CategoryCreate, CategoryUpdate, AuditLogResponse,
    PermissionResponse, PermissionUpdateRequest,
    LoginRequest, LoginResponse,
)
from backend_femi.services.notification_service import NotificationService
from backend_femi.utils.response import success_response, error_response, paginated_response
from backend_femi.core.security import verify_password, create_access_token, create_refresh_token

router = APIRouter(prefix="/api/nafdac", tags=["NAFDAC"])

# ─── Export directory ─────────────────────────────────────
EXPORT_DIR = "/tmp/sabilens_exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

# ─── In-memory config (demo) ──────────────────────────────
RISK_CONFIG = {
    "counterfeit_threshold": 0.7,
    "suspicious_threshold": 0.4,
    "auto_escalate_critical": True,
    "alert_on_recurring": True,
}

PERMISSIONS: dict = {
    "nafdac_admin": [
        "manage_officers", "verify_companies", "manage_alerts",
        "manage_cases", "manage_vendors", "view_analytics",
        "export_data", "manage_enforcement", "manage_settings",
        "broadcast_notifications",
    ],
    "nafdac_officer": [
        "view_companies", "manage_alerts", "manage_cases",
        "manage_vendors", "view_analytics", "export_data",
    ],
}


# ═══════════════════════════════════════════════════════════
# 1. AUTH & OFFICER MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.post("/login")
async def nafdac_login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login for NAFDAC officers and admins."""
    try:
        stmt = select(User).where(
            and_(
                User.role.in_(["nafdac_officer", "nafdac_admin"]),
                User.deleted_at.is_(None),
                or_(User.email == req.identifier, User.phone == req.identifier)
            )
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(req.password, user.password_hash):
            return error_response("Invalid credentials", code="INVALID_CREDENTIALS", status_code=401)

        if user.status != "active":
            return error_response("Account is not active", code="ACCOUNT_INACTIVE", status_code=403)

        user.last_login = datetime.utcnow()
        await db.commit()

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return success_response(
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "phone": user.phone,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "status": user.status,
                },
            },
            message="Login successful"
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/bootstrap/register")
async def bootstrap_register_officer(
    req: BootstrapOfficerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Bootstrap endpoint to create initial NAFDAC admin/officer before first login."""
    try:
        if req.setup_key != settings.NAFDAC_BOOTSTRAP_KEY:
            return error_response("Invalid setup key", code="INVALID_SETUP_KEY", status_code=403)

        exists_stmt = select(User).where(
            and_(
                User.deleted_at.is_(None),
                or_(User.email == req.email, User.phone == req.phone)
            )
        )
        existing_user = (await db.execute(exists_stmt)).scalar_one_or_none()
        if existing_user:
            return error_response(
                "User with this email or phone already exists",
                code="USER_EXISTS",
                status_code=409
            )

        from backend_femi.core.security import hash_password

        user = User(
            email=req.email,
            phone=req.phone,
            password_hash=hash_password(req.password),
            first_name=req.first_name,
            last_name=req.last_name,
            role=req.role,
            status="active",
        )
        db.add(user)

        audit = AuditLog(
            action="bootstrap_officer_created",
            entity_type="user",
            new_data={"email": req.email, "phone": req.phone, "role": req.role},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(user)

        return success_response(
            data={"id": str(user.id), "email": user.email, "role": user.role},
            message="Bootstrap user created successfully",
            status_code=201,
        )
    except ValueError as e:
        return error_response(str(e), code="INVALID_PASSWORD", status_code=422)
    except IntegrityError:
        await db.rollback()
        return error_response(
            "User with this email or phone already exists",
            code="USER_EXISTS",
            status_code=409,
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/officers")
async def create_officer(
    req: OfficerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    """Create a new NAFDAC officer. Admin only."""
    try:
        exists_stmt = select(User).where(
            and_(
                User.deleted_at.is_(None),
                or_(User.email == req.email, User.phone == req.phone)
            )
        )
        existing_user = (await db.execute(exists_stmt)).scalar_one_or_none()
        if existing_user:
            return error_response(
                "User with this email or phone already exists",
                code="USER_EXISTS",
                status_code=409
            )

        from backend_femi.core.security import hash_password

        officer = User(
            email=req.email,
            phone=req.phone,
            password_hash=hash_password(req.password),
            first_name=req.first_name,
            last_name=req.last_name,
            role=req.role,
            status="active",
        )
        db.add(officer)

        audit = AuditLog(
            user_id=current_user.id,
            action="officer_created",
            entity_type="user",
            new_data={"email": req.email, "role": req.role},
        )
        db.add(audit)
        await db.commit()
        await db.refresh(officer)

        return success_response(
            data={"id": str(officer.id), "email": officer.email, "role": officer.role},
            message="Officer created successfully"
        )
    except ValueError as e:
        return error_response(str(e), code="INVALID_PASSWORD", status_code=422)
    except IntegrityError:
        await db.rollback()
        return error_response(
            "User with this email or phone already exists",
            code="USER_EXISTS",
            status_code=409,
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/officers")
async def list_officers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    """List all NAFDAC officers. Admin only."""
    try:
        conditions = [
            User.role.in_(["nafdac_officer", "nafdac_admin"]),
            User.deleted_at.is_(None),
        ]
        count_stmt = select(func.count(User.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(User)
            .where(and_(*conditions))
            .order_by(User.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        officers = result.scalars().all()

        data = [
            {
                "id": str(o.id), "email": o.email, "phone": o.phone,
                "first_name": o.first_name, "last_name": o.last_name,
                "role": o.role, "status": o.status,
                "last_login": o.last_login.isoformat() if o.last_login else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in officers
        ]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.put("/officers/{officer_id}")
async def update_officer(
    officer_id: UUID,
    req: OfficerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    """Update officer details. Admin only."""
    try:
        officer = await db.get(User, officer_id)
        if not officer or officer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Officer not found")

        old_data = {"role": officer.role, "status": officer.status}
        if req.first_name is not None:
            officer.first_name = req.first_name
        if req.last_name is not None:
            officer.last_name = req.last_name
        if req.email is not None:
            officer.email = req.email
        if req.phone is not None:
            officer.phone = req.phone
        if req.status is not None:
            officer.status = req.status
        if req.role is not None:
            officer.role = req.role

        audit = AuditLog(
            user_id=current_user.id,
            action="officer_updated",
            entity_type="user",
            entity_id=officer_id,
            old_data=old_data,
            new_data=req.model_dump(exclude_none=True),
        )
        db.add(audit)
        await db.commit()

        return success_response(
            data={"id": str(officer.id), "role": officer.role, "status": officer.status},
            message="Officer updated"
        )
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.delete("/officers/{officer_id}")
async def delete_officer(
    officer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    """Soft-delete an officer. Admin only."""
    try:
        officer = await db.get(User, officer_id)
        if not officer or officer.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Officer not found")

        officer.deleted_at = datetime.utcnow()
        officer.status = "deleted"

        audit = AuditLog(
            user_id=current_user.id,
            action="officer_deleted",
            entity_type="user",
            entity_id=officer_id,
            old_data={"status": "active"},
            new_data={"status": "deleted"},
        )
        db.add(audit)
        await db.commit()

        return success_response(message="Officer deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/permissions")
async def get_permissions(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    """Return permissions mapping for all NAFDAC roles."""
    data = [{"role": role, "permissions": perms} for role, perms in PERMISSIONS.items()]
    return success_response(data=data)


@router.put("/permissions/{role}")
async def update_permissions(
    role: str,
    req: PermissionUpdateRequest,
    current_user: User = Depends(require_role("nafdac_admin"))
):
    """Update permissions for a role. Admin only."""
    global PERMISSIONS
    if role not in PERMISSIONS:
        raise HTTPException(status_code=404, detail="Role not found")
    PERMISSIONS[role] = req.permissions
    return success_response(
        data={"role": role, "permissions": PERMISSIONS[role]},
        message="Permissions updated"
    )


# ═══════════════════════════════════════════════════════════
# 2. COMPANY MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.get("/companies/stats")
async def company_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(Company.status, func.count(Company.id)).group_by(Company.status)
        result = await db.execute(stmt)
        rows = result.all()

        counts = {row[0]: row[1] for row in rows}
        total = sum(counts.values())

        return success_response(data={
            "total_companies": total,
            "active_companies": counts.get("active", 0),
            "pending_companies": counts.get("pending", 0),
            "suspended_companies": counts.get("suspended", 0),
            "rejected_companies": counts.get("rejected", 0),
        })
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/companies/pending")
async def list_pending_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        count_stmt = select(func.count(Company.id)).where(Company.status == "pending")
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Company)
            .where(Company.status == "pending")
            .order_by(Company.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        companies = result.scalars().all()

        data = [_company_to_dict(c) for c in companies]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/companies/{company_id}")
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        company = await db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return success_response(data=_company_to_dict(company, detail=True))
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/companies")
async def list_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [Company.status != "rejected"]
        if status:
            conditions = [Company.status == status]

        count_stmt = select(func.count(Company.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Company)
            .where(and_(*conditions))
            .order_by(Company.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        companies = result.scalars().all()

        data = [_company_to_dict(c) for c in companies]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/companies/{company_id}/verify")
async def verify_company(
    company_id: UUID,
    req: CompanyVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        company = await db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        old_status = company.status
        company.status = "active"
        company.verified_at = datetime.utcnow()
        company.verified_by = current_user.id

        db.add(AuditLog(
            user_id=current_user.id,
            action="company_verified",
            entity_type="company",
            entity_id=company_id,
            old_data={"status": old_status},
            new_data={"status": "active", "notes": req.notes},
        ))
        await db.commit()
        return success_response(message="Company verified successfully")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/companies/{company_id}/reject")
async def reject_company(
    company_id: UUID,
    req: CompanyRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        company = await db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        old_status = company.status
        company.status = "rejected"

        db.add(AuditLog(
            user_id=current_user.id,
            action="company_rejected",
            entity_type="company",
            entity_id=company_id,
            old_data={"status": old_status},
            new_data={"status": "rejected", "reason": req.reason},
        ))
        await db.commit()
        return success_response(message="Company rejected")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.put("/companies/{company_id}/suspend")
async def suspend_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    return await _set_company_status(company_id, "suspended", "company_suspended", db, current_user)


@router.put("/companies/{company_id}/activate")
async def activate_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    return await _set_company_status(company_id, "active", "company_activated", db, current_user)


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        company = await db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        old_status = company.status
        company.status = "rejected"  # soft-delete via status

        db.add(AuditLog(
            user_id=current_user.id,
            action="company_deleted",
            entity_type="company",
            entity_id=company_id,
            old_data={"status": old_status},
            new_data={"status": "deleted"},
        ))
        await db.commit()
        return success_response(message="Company removed")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 3. NATIONAL DASHBOARD
# ═══════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        total_scans = (await db.execute(select(func.count(Scan.id)))).scalar() or 0
        total_reports = (await db.execute(select(func.count(Report.id)))).scalar() or 0
        counterfeit_scans = (await db.execute(
            select(func.count(Scan.id)).where(Scan.status == "fake")
        )).scalar() or 0
        authentic_scans = (await db.execute(
            select(func.count(Scan.id)).where(Scan.status == "authentic")
        )).scalar() or 0
        suspicious_scans = (await db.execute(
            select(func.count(Scan.id)).where(Scan.status == "suspicious")
        )).scalar() or 0
        active_companies = (await db.execute(
            select(func.count(Company.id)).where(Company.status == "active")
        )).scalar() or 0
        active_alerts = (await db.execute(
            select(func.count(Alert.id)).where(Alert.is_acknowledged == False)
        )).scalar() or 0
        resolved_cases = (await db.execute(
            select(func.count(Report.id)).where(Report.report_status == "resolved")
        )).scalar() or 0

        return success_response(data={
            "total_scans": total_scans,
            "total_reports": total_reports,
            "total_counterfeit": counterfeit_scans,
            "total_authentic": authentic_scans,
            "total_suspicious": suspicious_scans,
            "active_companies": active_companies,
            "active_alerts": active_alerts,
            "resolved_cases": resolved_cases,
        })
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    """Same as /dashboard, structured as KPI cards."""
    return await get_dashboard(db=db, current_user=current_user)


@router.get("/dashboard/heatmap")
async def get_heatmap(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        try:
            from geoalchemy2.functions import ST_X, ST_Y
            from sqlalchemy import cast
            from geoalchemy2.types import Geometry
            stmt = select(
                Hotspot.id,
                Hotspot.region_name,
                Hotspot.city,
                Hotspot.state,
                Hotspot.report_count,
                Hotspot.severity_score,
                Hotspot.risk_level,
                ST_Y(cast(Hotspot.location, Geometry)).label("latitude"),
                ST_X(cast(Hotspot.location, Geometry)).label("longitude"),
            ).where(Hotspot.risk_level.in_(["critical", "high", "medium"]))
        except Exception:
            # Fallback: lat/lng columns
            stmt = select(Hotspot).where(
                Hotspot.risk_level.in_(["critical", "high", "medium"])
            ).order_by(Hotspot.severity_score.desc())

        result = await db.execute(stmt)
        rows = result.all()

        hotspots = []
        for row in rows:
            if hasattr(row, "_mapping"):
                m = dict(row._mapping)
                hotspots.append({
                    "id": str(m.get("id")),
                    "latitude": float(m.get("latitude") or 0),
                    "longitude": float(m.get("longitude") or 0),
                    "region_name": m.get("region_name"),
                    "city": m.get("city"),
                    "state": m.get("state"),
                    "report_count": m.get("report_count", 0),
                    "severity_score": float(m.get("severity_score") or 0),
                    "risk_level": m.get("risk_level"),
                })
            else:
                hotspot = row
                hotspots.append({
                    "id": str(hotspot.id),
                    "latitude": float(getattr(hotspot, "location_lat", 0) or 0),
                    "longitude": float(getattr(hotspot, "location_lng", 0) or 0),
                    "region_name": hotspot.region_name,
                    "city": hotspot.city,
                    "state": hotspot.state,
                    "report_count": hotspot.report_count,
                    "severity_score": float(hotspot.severity_score or 0),
                    "risk_level": hotspot.risk_level,
                })

        return success_response(data=hotspots)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/dashboard/live-alerts")
async def get_live_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = (
            select(Alert)
            .where(Alert.is_acknowledged == False)
            .order_by(Alert.created_at.desc())
            .limit(20)
        )
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        data = [_alert_to_dict(a) for a in alerts]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/dashboard/regions")
async def get_dashboard_regions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = (
            select(AnalyticsRegion)
            .where(AnalyticsRegion.period == "monthly")
            .order_by(AnalyticsRegion.counterfeit_count.desc())
        )
        result = await db.execute(stmt)
        regions = result.scalars().all()

        data = [
            {
                "state": r.state,
                "city": r.city,
                "scan_count": r.scan_count,
                "counterfeit_count": r.counterfeit_count,
                "risk_score": float(r.risk_score) if r.risk_score else None,
            }
            for r in regions
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        thirty_days_ago = date.today() - timedelta(days=30)
        stmt = (
            select(AnalyticsDaily)
            .where(AnalyticsDaily.date >= thirty_days_ago)
            .order_by(AnalyticsDaily.date)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        data = [
            {
                "date": str(r.date),
                "total_scans": r.total_scans,
                "counterfeit_scans": r.counterfeit_scans,
                "authentic_scans": r.authentic_scans,
                "suspicious_scans": r.suspicious_scans,
            }
            for r in rows
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 4. ALERT MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.get("/alerts/stats")
async def get_alert_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(
            func.count(Alert.id).label("total"),
            func.count(case((Alert.severity == "critical", 1))).label("critical"),
            func.count(case((Alert.severity == "high", 1))).label("high"),
            func.count(case((Alert.severity == "medium", 1))).label("medium"),
            func.count(case((Alert.severity == "low", 1))).label("low"),
            func.count(case((Alert.is_acknowledged == False, 1))).label("unacknowledged"),
            func.count(case((Alert.is_acknowledged == True, 1))).label("acknowledged"),
        )
        result = await db.execute(stmt)
        row = result.one()

        return success_response(data={
            "total_alerts": row.total,
            "critical_alerts": row.critical,
            "high_alerts": row.high,
            "medium_alerts": row.medium,
            "low_alerts": row.low,
            "unacknowledged": row.unacknowledged,
            "acknowledged": row.acknowledged,
        })
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/alerts/critical")
async def get_critical_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [Alert.severity == "critical", Alert.is_acknowledged == False]
        count_stmt = select(func.count(Alert.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Alert)
            .where(and_(*conditions))
            .order_by(Alert.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        return paginated_response(data=[_alert_to_dict(a) for a in alerts], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/alerts/export")
async def export_alerts(
    format: str = Query("csv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(Alert).order_by(Alert.created_at.desc())
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        export_id = _uuid.uuid4()
        filepath = os.path.join(EXPORT_DIR, f"{export_id}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "alert_type", "severity", "title", "is_acknowledged", "created_at"])
            for a in alerts:
                writer.writerow([str(a.id), a.alert_type, a.severity, a.title, a.is_acknowledged, str(a.created_at)])

        return success_response(data={
            "export_id": str(export_id),
            "status": "completed",
            "file_url": f"/api/nafdac/export/download/{export_id}",
        }, message="Export ready")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        alert = await db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return success_response(data=_alert_to_dict(alert))
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/alerts")
async def list_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_acknowledged: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = []
        if alert_type:
            conditions.append(Alert.alert_type == alert_type)
        if severity:
            conditions.append(Alert.severity == severity)
        if is_acknowledged is not None:
            conditions.append(Alert.is_acknowledged == is_acknowledged)
        if date_from:
            conditions.append(Alert.created_at >= date_from)
        if date_to:
            conditions.append(Alert.created_at <= date_to)

        count_stmt = select(func.count(Alert.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(Alert).order_by(Alert.created_at.desc()).offset((page - 1) * limit).limit(limit)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        return paginated_response(data=[_alert_to_dict(a) for a in alerts], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    req: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        alert = await db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_acknowledged = True
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()
        await db.commit()

        return success_response(data=_alert_to_dict(alert), message="Alert acknowledged")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    req: AlertResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        alert = await db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_acknowledged = True
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()

        # Also resolve the linked report
        if alert.report_id:
            report = await db.get(Report, alert.report_id)
            if report:
                report.report_status = "resolved"
                report.resolved_at = datetime.utcnow()
                report.resolved_by = current_user.id
                report.resolution_notes = req.resolution_notes

        await db.commit()
        return success_response(message="Alert resolved")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/alerts/bulk-acknowledge")
async def bulk_acknowledge_alerts(
    req: BulkAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = (
            update(Alert)
            .where(Alert.id.in_(req.alert_ids))
            .values(
                is_acknowledged=True,
                acknowledged_by=current_user.id,
                acknowledged_at=datetime.utcnow(),
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return success_response(data={"updated": result.rowcount}, message="Bulk acknowledge complete")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 5. CASES & EVIDENCE
# ═══════════════════════════════════════════════════════════

@router.get("/cases/stats")
async def get_cases_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(Report.report_status, func.count(Report.id)).group_by(Report.report_status)
        result = await db.execute(stmt)
        rows = result.all()
        counts = {row[0]: row[1] for row in rows}
        return success_response(data={"by_status": counts, "total": sum(counts.values())})
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/cases/search")
async def search_cases(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = []
        if query:
            conditions.append(
                or_(
                    Report.additional_comments.ilike(f"%{query}%"),
                    Report.location_name.ilike(f"%{query}%"),
                )
            )
        if status:
            conditions.append(Report.report_status == status)
        if severity:
            conditions.append(Report.severity == severity)
        if state:
            conditions.append(Report.location_name.ilike(f"%{state}%"))
        if date_from:
            conditions.append(Report.reported_at >= date_from)
        if date_to:
            conditions.append(Report.reported_at <= date_to)

        count_stmt = select(func.count(Report.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(Report).order_by(Report.reported_at.desc()).offset((page - 1) * limit).limit(limit)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await db.execute(stmt)
        reports = result.scalars().all()

        return paginated_response(data=[_report_to_dict(r) for r in reports], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/cases/{case_id}/evidence")
async def get_case_evidence(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(ReportEvidence).where(ReportEvidence.report_id == case_id)
        result = await db.execute(stmt)
        evidence = result.scalars().all()
        data = [
            {
                "id": str(e.id),
                "file_url": e.file_url,
                "file_type": e.file_type,
                "description": e.description,
                "created_at": str(e.created_at),
            }
            for e in evidence
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/cases/{case_id}/assign")
async def assign_case(
    case_id: UUID,
    req: CaseAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        report = await db.get(Report, case_id)
        if not report:
            raise HTTPException(status_code=404, detail="Case not found")

        db.add(AuditLog(
            user_id=current_user.id,
            action="case_assigned",
            entity_type="report",
            entity_id=case_id,
            new_data={"assigned_to": str(req.officer_id), "notes": req.notes},
        ))
        await db.commit()
        return success_response(message="Case assigned successfully")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/cases/{case_id}/update-status")
async def update_case_status(
    case_id: UUID,
    req: CaseStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        report = await db.get(Report, case_id)
        if not report:
            raise HTTPException(status_code=404, detail="Case not found")

        old_status = report.report_status
        report.report_status = req.status.value
        if req.status.value == "resolved":
            report.resolved_at = datetime.utcnow()
            report.resolved_by = current_user.id
            if req.notes:
                report.resolution_notes = req.notes

        db.add(AuditLog(
            user_id=current_user.id,
            action="case_status_updated",
            entity_type="report",
            entity_id=case_id,
            old_data={"status": old_status},
            new_data={"status": req.status.value, "notes": req.notes},
        ))
        await db.commit()
        return success_response(message=f"Case status updated to {req.status.value}")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/cases/export")
async def export_cases(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(Report)
        if req.date_from:
            stmt = stmt.where(Report.reported_at >= req.date_from)
        if req.date_to:
            stmt = stmt.where(Report.reported_at <= req.date_to)

        result = await db.execute(stmt)
        reports = result.scalars().all()

        export_id = _uuid.uuid4()
        filepath = os.path.join(EXPORT_DIR, f"{export_id}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "status", "severity", "location", "reported_at"])
            for r in reports:
                writer.writerow([str(r.id), r.report_status, r.severity, r.location_name, str(r.reported_at)])

        return success_response(data={
            "export_id": str(export_id),
            "status": "completed",
            "file_url": f"/api/nafdac/export/download/{export_id}",
        }, message="Export completed")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/cases/{case_id}")
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        report = await db.get(Report, case_id)
        if not report:
            raise HTTPException(status_code=404, detail="Case not found")
        return success_response(data=_report_to_dict(report))
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/cases")
async def list_cases(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = []
        if status:
            conditions.append(Report.report_status == status)

        count_stmt = select(func.count(Report.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(Report).order_by(Report.reported_at.desc()).offset((page - 1) * limit).limit(limit)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await db.execute(stmt)
        reports = result.scalars().all()

        return paginated_response(data=[_report_to_dict(r) for r in reports], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 6. VENDOR TRACKING
# ═══════════════════════════════════════════════════════════

@router.get("/vendors/stats")
async def get_vendor_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        total = (await db.execute(select(func.count(VendorLocation.id)))).scalar() or 0
        high_risk = (await db.execute(
            select(func.count(VendorLocation.id)).where(
                VendorLocation.risk_level.in_(["critical", "high"])
            )
        )).scalar() or 0
        blacklisted = (await db.execute(
            select(func.count(VendorLocation.id)).where(VendorLocation.is_blacklisted == True)
        )).scalar() or 0
        recurring = (await db.execute(
            select(func.count(VendorLocation.id)).where(VendorLocation.report_count >= 3)
        )).scalar() or 0

        return success_response(data={
            "total_vendors": total,
            "high_risk_vendors": high_risk,
            "blacklisted_vendors": blacklisted,
            "recurring_offenders": recurring,
        })
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/vendors/high-risk")
async def get_high_risk_vendors(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [VendorLocation.risk_level.in_(["critical", "high"])]
        count_stmt = select(func.count(VendorLocation.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(VendorLocation)
            .where(and_(*conditions))
            .order_by(VendorLocation.last_reported_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        vendors = result.scalars().all()

        return paginated_response(data=[_vendor_to_dict(v) for v in vendors], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/vendors/recurring")
async def get_recurring_vendors(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [VendorLocation.report_count >= 3]
        count_stmt = select(func.count(VendorLocation.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(VendorLocation)
            .where(and_(*conditions))
            .order_by(VendorLocation.report_count.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        vendors = result.scalars().all()

        return paginated_response(data=[_vendor_to_dict(v) for v in vendors], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/vendors/export")
async def export_vendors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(VendorLocation).order_by(VendorLocation.last_reported_at.desc())
        result = await db.execute(stmt)
        vendors = result.scalars().all()

        export_id = _uuid.uuid4()
        filepath = os.path.join(EXPORT_DIR, f"{export_id}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "vendor_name", "city", "state", "risk_level", "is_blacklisted", "report_count"])
            for v in vendors:
                writer.writerow([str(v.id), v.vendor_name, v.city, v.state, v.risk_level, v.is_blacklisted, v.report_count])

        return success_response(data={
            "export_id": str(export_id),
            "status": "completed",
            "file_url": f"/api/nafdac/export/download/{export_id}",
        }, message="Export ready")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        vendor = await db.get(VendorLocation, vendor_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        return success_response(data=_vendor_to_dict(vendor))
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/vendors")
async def list_vendors(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        count_stmt = select(func.count(VendorLocation.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(VendorLocation)
            .order_by(VendorLocation.last_reported_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        vendors = result.scalars().all()

        return paginated_response(data=[_vendor_to_dict(v) for v in vendors], page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/vendors/{vendor_id}/blacklist")
async def blacklist_vendor(
    vendor_id: UUID,
    req: VendorBlacklistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        vendor = await db.get(VendorLocation, vendor_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        vendor.is_blacklisted = True
        vendor.blacklisted_at = datetime.utcnow()
        vendor.blacklisted_by = current_user.id

        # Create alert if vendor has associated company via report
        if vendor.report_id:
            report = await db.get(Report, vendor.report_id)
            if report and report.company_id:
                await NotificationService.create_alert(
                    db,
                    company_id=report.company_id,
                    report_id=vendor.report_id,
                    alert_type="counterfeit",
                    severity="high",
                    title="Vendor Blacklisted",
                    message=f"Vendor '{vendor.vendor_name}' has been blacklisted. Reason: {req.reason}",
                    metadata={"vendor_id": str(vendor_id), "reason": req.reason},
                )

        db.add(AuditLog(
            user_id=current_user.id,
            action="vendor_blacklisted",
            entity_type="vendor_location",
            entity_id=vendor_id,
            new_data={"reason": req.reason},
        ))
        await db.commit()
        return success_response(message="Vendor blacklisted successfully")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/vendors/{vendor_id}/investigate")
async def investigate_vendor(
    vendor_id: UUID,
    req: VendorInvestigateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        vendor = await db.get(VendorLocation, vendor_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        if req.priority:
            vendor.risk_level = req.priority.value

        db.add(AuditLog(
            user_id=current_user.id,
            action="vendor_investigation_opened",
            entity_type="vendor_location",
            entity_id=vendor_id,
            new_data={"notes": req.notes, "priority": req.priority.value if req.priority else None},
        ))
        await db.commit()
        return success_response(message="Vendor investigation opened")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 7. ANALYTICS
# ═══════════════════════════════════════════════════════════

@router.get("/analytics/categories")
async def get_category_analytics(
    period: Optional[str] = Query("monthly"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = []
        if period:
            conditions.append(AnalyticsCategory.period == period)
        if date_from:
            conditions.append(AnalyticsCategory.period_start >= date_from)
        if date_to:
            conditions.append(AnalyticsCategory.period_end <= date_to)

        stmt = select(AnalyticsCategory).order_by(AnalyticsCategory.scan_count.desc())
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await db.execute(stmt)
        categories = result.scalars().all()

        data = [
            {
                "category_name": c.category_name,
                "scan_count": c.scan_count,
                "counterfeit_count": c.counterfeit_count,
                "suspicious_count": c.suspicious_count,
                "authentic_count": c.authentic_count,
                "period_start": str(c.period_start),
                "period_end": str(c.period_end),
            }
            for c in categories
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/analytics/trends")
async def get_analytics_trends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        today = date.today()

        current_stmt = (
            select(AnalyticsDaily)
            .where(AnalyticsDaily.date >= today - timedelta(days=30))
            .order_by(AnalyticsDaily.date)
        )
        previous_stmt = (
            select(AnalyticsDaily)
            .where(and_(
                AnalyticsDaily.date >= today - timedelta(days=60),
                AnalyticsDaily.date < today - timedelta(days=30),
            ))
            .order_by(AnalyticsDaily.date)
        )

        def serialize_daily(rows):
            return [
                {
                    "date": str(r.date),
                    "total_scans": r.total_scans,
                    "counterfeit_scans": r.counterfeit_scans,
                    "authentic_scans": r.authentic_scans,
                    "suspicious_scans": r.suspicious_scans,
                }
                for r in rows
            ]

        current_result = (await db.execute(current_stmt)).scalars().all()
        previous_result = (await db.execute(previous_stmt)).scalars().all()

        return success_response(data={
            "current_period": serialize_daily(current_result),
            "previous_period": serialize_daily(previous_result),
        })
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/analytics/regions")
async def get_analytics_regions(
    period: Optional[str] = Query("monthly"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(AnalyticsRegion)
        if period:
            stmt = stmt.where(AnalyticsRegion.period == period)
        stmt = stmt.order_by(AnalyticsRegion.counterfeit_count.desc())
        result = await db.execute(stmt)
        regions = result.scalars().all()

        data = [
            {
                "state": r.state,
                "city": r.city,
                "scan_count": r.scan_count,
                "counterfeit_count": r.counterfeit_count,
                "risk_score": float(r.risk_score) if r.risk_score else None,
            }
            for r in regions
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/analytics/timeline")
async def get_analytics_timeline(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        today = date.today()
        d_from = date_from or (today - timedelta(days=30))
        d_to = date_to or today

        stmt = (
            select(AnalyticsDaily)
            .where(AnalyticsDaily.date.between(d_from, d_to))
            .order_by(AnalyticsDaily.date)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        data = [
            {
                "date": str(r.date),
                "events": r.total_scans + r.total_reports,
                "scans": r.total_scans,
                "reports": r.total_reports,
                "alerts": 0,  # Could join alerts table; placeholder for demo
            }
            for r in rows
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/analytics/export")
async def export_analytics(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(AnalyticsDaily)
        if req.date_from:
            stmt = stmt.where(AnalyticsDaily.date >= req.date_from)
        if req.date_to:
            stmt = stmt.where(AnalyticsDaily.date <= req.date_to)
        result = await db.execute(stmt)
        rows = result.scalars().all()

        export_id = _uuid.uuid4()
        filepath = os.path.join(EXPORT_DIR, f"{export_id}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "total_scans", "authentic_scans", "suspicious_scans", "counterfeit_scans", "total_reports"])
            for r in rows:
                writer.writerow([r.date, r.total_scans, r.authentic_scans, r.suspicious_scans, r.counterfeit_scans, r.total_reports])

        return success_response(data={
            "export_id": str(export_id),
            "status": "completed",
            "file_url": f"/api/nafdac/export/download/{export_id}",
        }, message="Analytics export completed")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/analytics/predictions")
async def get_predictions(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    """Return mocked AI predictions for demo."""
    predictions = [
        {"state": "Lagos", "predicted_risk_level": "high", "predicted_counterfeit_increase_pct": 12.5, "confidence": 0.82},
        {"state": "Kano", "predicted_risk_level": "medium", "predicted_counterfeit_increase_pct": 8.3, "confidence": 0.75},
        {"state": "Rivers", "predicted_risk_level": "high", "predicted_counterfeit_increase_pct": 15.1, "confidence": 0.79},
        {"state": "Oyo", "predicted_risk_level": "low", "predicted_counterfeit_increase_pct": 3.2, "confidence": 0.88},
        {"state": "Abuja FCT", "predicted_risk_level": "medium", "predicted_counterfeit_increase_pct": 6.7, "confidence": 0.77},
    ]
    return success_response(data=predictions, message="AI predictions retrieved")


@router.get("/analytics/hotspots")
async def get_analytics_hotspots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(Hotspot).order_by(Hotspot.severity_score.desc()).limit(50)
        result = await db.execute(stmt)
        hotspots = result.scalars().all()

        data = []
        for h in hotspots:
            data.append({
                "id": str(h.id),
                "latitude": float(getattr(h, "location_lat", 0) or 0),
                "longitude": float(getattr(h, "location_lng", 0) or 0),
                "region_name": h.region_name,
                "city": h.city,
                "state": h.state,
                "report_count": h.report_count,
                "severity_score": float(h.severity_score) if h.severity_score else None,
                "risk_level": h.risk_level,
            })
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 8. EXPORT SYSTEM
# ═══════════════════════════════════════════════════════════

@router.get("/export")
async def list_exports(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    """List available exports (demo: scan EXPORT_DIR)."""
    try:
        files = os.listdir(EXPORT_DIR) if os.path.exists(EXPORT_DIR) else []
        exports = [{"export_id": f.replace(".csv", ""), "file_url": f"/api/nafdac/export/download/{f.replace('.csv', '')}"} for f in files if f.endswith(".csv")]
        return success_response(data=exports)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/export/reports")
async def export_reports(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return await export_cases(req=req, db=db, current_user=current_user)


@router.post("/export/vendors")
async def export_vendors_post(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return await export_vendors(db=db, current_user=current_user)


@router.post("/export/analytics")
async def export_analytics_post(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return await export_analytics(req=req, db=db, current_user=current_user)


@router.post("/export/cases")
async def export_cases_post(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return await export_cases(req=req, db=db, current_user=current_user)


@router.get("/export/history")
async def export_history(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return await list_exports(current_user=current_user)


@router.get("/export/download/{export_id}")
async def download_export(
    export_id: UUID,
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    filepath = os.path.join(EXPORT_DIR, f"{export_id}.csv")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(filepath, media_type="text/csv", filename=f"sabilens_export_{export_id}.csv")


# ═══════════════════════════════════════════════════════════
# 9. ENFORCEMENT ACTIONS
# ═══════════════════════════════════════════════════════════

@router.post("/enforcement/raids")
async def schedule_raid(
    req: RaidScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        raid_id = _uuid.uuid4()
        raid_data = {
            "raid_id": str(raid_id),
            "location_name": req.location_name,
            "address": req.address,
            "state": req.state,
            "city": req.city,
            "scheduled_date": req.scheduled_date.isoformat(),
            "assigned_officers": [str(o) for o in req.assigned_officers],
            "notes": req.notes,
            "priority": req.priority.value,
            "status": "scheduled",
        }
        db.add(AuditLog(
            user_id=current_user.id,
            action="raid_scheduled",
            entity_type="enforcement_raid",
            entity_id=raid_id,
            new_data=raid_data,
        ))
        await db.commit()
        return success_response(data=raid_data, message="Raid scheduled successfully")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/enforcement/raids")
async def list_raids(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [AuditLog.entity_type == "enforcement_raid"]
        count_stmt = select(func.count(AuditLog.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        data = [log.new_data for log in logs if log.new_data]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.put("/enforcement/raids/{raid_id}")
async def update_raid(
    raid_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        stmt = select(AuditLog).where(
            and_(
                AuditLog.entity_type == "enforcement_raid",
                AuditLog.entity_id == raid_id,
            )
        )
        result = await db.execute(stmt)
        log = result.scalar_one_or_none()
        if not log:
            raise HTTPException(status_code=404, detail="Raid not found")

        return success_response(data=log.new_data, message="Raid retrieved (update via new audit log entry)")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/enforcement/notices")
async def send_warning_notice(
    req: WarningNoticeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        notice_id = _uuid.uuid4()
        notice_data = {
            "notice_id": str(notice_id),
            "company_id": str(req.company_id),
            "subject": req.subject,
            "message": req.message,
            "severity": req.severity.value,
            "deadline_date": str(req.deadline_date) if req.deadline_date else None,
            "status": "sent",
        }
        db.add(AuditLog(
            user_id=current_user.id,
            action="warning_notice_sent",
            entity_type="enforcement_notice",
            entity_id=notice_id,
            new_data=notice_data,
        ))

        # Notify the company
        count = await NotificationService.send_to_company(
            db, req.company_id, req.subject, req.message
        )
        await db.commit()

        return success_response(
            data={**notice_data, "notifications_sent": count},
            message="Warning notice sent"
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/enforcement/history")
async def enforcement_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        conditions = [AuditLog.entity_type.in_(["enforcement_raid", "enforcement_notice", "enforcement_seizure"])]
        count_stmt = select(func.count(AuditLog.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()

        data = [
            {
                "id": str(log.id),
                "action": log.action,
                "entity_type": log.entity_type,
                "created_at": str(log.created_at),
                "data": log.new_data,
            }
            for log in logs
        ]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/enforcement/seizures")
async def log_seizure(
    req: SeizureLogRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        seizure_id = _uuid.uuid4()
        seizure_data = {
            "seizure_id": str(seizure_id),
            "vendor_id": str(req.vendor_id) if req.vendor_id else None,
            "product_name": req.product_name,
            "quantity": req.quantity,
            "location_name": req.location_name,
            "state": req.state,
            "city": req.city,
            "officer_notes": req.officer_notes,
            "evidence_urls": req.evidence_urls,
            "status": "logged",
        }
        db.add(AuditLog(
            user_id=current_user.id,
            action="seizure_logged",
            entity_type="enforcement_seizure",
            entity_id=seizure_id,
            new_data=seizure_data,
        ))
        await db.commit()
        return success_response(data=seizure_data, message="Seizure logged successfully")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 10. NAFDAC NOTIFICATIONS
# ═══════════════════════════════════════════════════════════

@router.get("/notifications")
async def get_nafdac_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        notifications, total = await NotificationService.get_user_notifications(
            db, current_user.id, page, limit
        )
        data = [
            {
                "id": str(n.id),
                "notification_type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": str(n.created_at),
            }
            for n in notifications
        ]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/notifications/broadcast")
async def broadcast_notification(
    req: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        count = await NotificationService.broadcast_to_all_companies(
            db, req.title, req.message,
            req.severity.value if req.severity else None
        )
        await db.commit()
        return success_response(
            data={"notifications_sent": count},
            message=f"Broadcast sent to {count} company admins"
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/notifications/company/{company_id}")
async def notify_company(
    company_id: UUID,
    req: CompanyNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        count = await NotificationService.send_to_company(
            db, company_id, req.title, req.message
        )
        await db.commit()
        return success_response(
            data={"notifications_sent": count},
            message=f"Notification sent to {count} company admins"
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/notifications/settings")
async def get_notification_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        prefs = await NotificationService.get_preferences(db, current_user.id)
        data = [
            {
                "id": str(p.id),
                "notification_type": p.notification_type,
                "channel": p.channel,
                "enabled": p.enabled,
            }
            for p in prefs
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.put("/notifications/settings")
async def update_notification_settings(
    req: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        pref = await NotificationService.update_preference(
            db, current_user.id, req.notification_type, req.channel, req.enabled
        )
        await db.commit()
        return success_response(
            data={"notification_type": pref.notification_type, "channel": pref.channel, "enabled": pref.enabled},
            message="Notification settings updated"
        )
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# 11. SETTINGS & CONFIGURATION
# ═══════════════════════════════════════════════════════════

@router.get("/settings")
async def get_settings(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return success_response(data={
        "risk_levels": RISK_CONFIG,
        "categories": [],
        "notification_defaults": {"email": True, "push": True, "sms": False, "in_app": True},
    })


@router.put("/settings")
async def update_settings(
    req: RiskLevelConfig,
    current_user: User = Depends(require_role("nafdac_admin"))
):
    global RISK_CONFIG
    RISK_CONFIG = req.model_dump()
    return success_response(data=RISK_CONFIG, message="Settings updated")


@router.get("/settings/risk-levels")
async def get_risk_levels(
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    return success_response(data=RISK_CONFIG)


@router.put("/settings/risk-levels")
async def update_risk_levels(
    req: RiskLevelConfig,
    current_user: User = Depends(require_role("nafdac_admin"))
):
    global RISK_CONFIG
    RISK_CONFIG = req.model_dump()
    return success_response(data=RISK_CONFIG, message="Risk levels updated")


@router.get("/settings/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin", "nafdac_officer"))
):
    try:
        stmt = select(ProductCategory).where(ProductCategory.is_active == True)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        data = [
            {
                "id": str(c.id),
                "name": c.name,
                "description": c.description,
                "parent_id": str(c.parent_id) if c.parent_id else None,
            }
            for c in categories
        ]
        return success_response(data=data)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.post("/settings/categories")
async def create_category(
    req: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        cat = ProductCategory(name=req.name, description=req.description, parent_id=req.parent_id)
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return success_response(data={"id": str(cat.id), "name": cat.name}, message="Category created")
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.put("/settings/categories/{category_id}")
async def update_category(
    category_id: UUID,
    req: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        cat = await db.get(ProductCategory, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        if req.name is not None:
            cat.name = req.name
        if req.description is not None:
            cat.description = req.description
        if req.is_active is not None:
            cat.is_active = req.is_active

        await db.commit()
        return success_response(data={"id": str(cat.id), "name": cat.name}, message="Category updated")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.delete("/settings/categories/{category_id}")
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        cat = await db.get(ProductCategory, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        cat.is_active = False
        await db.commit()
        return success_response(message="Category deactivated")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


@router.get("/settings/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("nafdac_admin"))
):
    try:
        conditions = []
        if entity_type:
            conditions.append(AuditLog.entity_type == entity_type)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action.ilike(f"%{action}%"))
        if date_from:
            conditions.append(AuditLog.created_at >= date_from)
        if date_to:
            conditions.append(AuditLog.created_at <= date_to)

        count_stmt = select(func.count(AuditLog.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.offset((page - 1) * limit).limit(limit)

        result = await db.execute(stmt)
        logs = result.scalars().all()

        data = [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id) if log.entity_id else None,
                "old_data": log.old_data,
                "new_data": log.new_data,
                "ip_address": log.ip_address,
                "created_at": str(log.created_at),
            }
            for log in logs
        ]
        return paginated_response(data=data, page=page, limit=limit, total=total)
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)


# ═══════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════

def _company_to_dict(company: Company, detail: bool = False) -> dict:
    base = {
        "id": str(company.id),
        "name": company.name,
        "registration_number": company.registration_number,
        "email": company.email,
        "status": company.status,
        "subscription_tier": company.subscription_tier,
        "verified_at": str(company.verified_at) if company.verified_at else None,
        "created_at": str(company.created_at) if company.created_at else None,
    }
    if detail:
        base.update({
            "phone": company.phone,
            "address": company.address,
            "city": company.city,
            "state": company.state,
            "country": company.country,
            "logo_url": company.logo_url,
            "website": company.website,
        })
    return base


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id": str(alert.id),
        "report_id": str(alert.report_id) if alert.report_id else None,
        "company_id": str(alert.company_id) if alert.company_id else None,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "metadata": alert.metadata_,
        "is_read": alert.is_read,
        "is_acknowledged": alert.is_acknowledged,
        "acknowledged_by": str(alert.acknowledged_by) if alert.acknowledged_by else None,
        "acknowledged_at": str(alert.acknowledged_at) if alert.acknowledged_at else None,
        "created_at": str(alert.created_at) if alert.created_at else None,
    }


def _report_to_dict(report: Report) -> dict:
    return {
        "id": str(report.id),
        "scan_id": str(report.scan_id),
        "user_id": str(report.user_id),
        "product_id": str(report.product_id) if report.product_id else None,
        "company_id": str(report.company_id) if report.company_id else None,
        "report_status": report.report_status,
        "severity": report.severity,
        "purchase_channel": report.purchase_channel,
        "price_paid": float(report.price_paid) if report.price_paid else None,
        "additional_comments": report.additional_comments,
        "location_name": report.location_name,
        "reported_at": str(report.reported_at) if report.reported_at else None,
        "resolved_at": str(report.resolved_at) if report.resolved_at else None,
        "resolved_by": str(report.resolved_by) if report.resolved_by else None,
        "resolution_notes": report.resolution_notes,
    }


def _vendor_to_dict(vendor: VendorLocation) -> dict:
    return {
        "id": str(vendor.id),
        "report_id": str(vendor.report_id) if vendor.report_id else None,
        "vendor_name": vendor.vendor_name,
        "address": vendor.address,
        "city": vendor.city,
        "state": vendor.state,
        "report_count": vendor.report_count,
        "risk_level": vendor.risk_level,
        "is_blacklisted": vendor.is_blacklisted,
        "blacklisted_at": str(vendor.blacklisted_at) if vendor.blacklisted_at else None,
        "last_reported_at": str(vendor.last_reported_at) if vendor.last_reported_at else None,
        "created_at": str(vendor.created_at) if vendor.created_at else None,
    }


async def _set_company_status(
    company_id: UUID, new_status: str, action: str,
    db: AsyncSession, current_user: User
):
    try:
        company = await db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        old_status = company.status
        company.status = new_status

        db.add(AuditLog(
            user_id=current_user.id,
            action=action,
            entity_type="company",
            entity_id=company_id,
            old_data={"status": old_status},
            new_data={"status": new_status},
        ))
        await db.commit()
        return success_response(message=f"Company {new_status} successfully")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(str(e), code="INTERNAL_ERROR", status_code=500)
