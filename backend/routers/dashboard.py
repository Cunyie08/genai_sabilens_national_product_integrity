"""
Admin Dashboard Router
======================
Intelligence dashboard endpoints for SabiLens.

ACCESS HIERARCHY:
  super_admin    : Full access. All companies, all products, all data.
  company_admin  : Own products only. Filtered by company_id from JWT.
  nafdac_admin   : Three free endpoints + gated access via data request.
  nafdac_officer : Same as nafdac_admin.
  consumer       : No dashboard access.

NAFDAC ACCESS MODEL - THREE FREE, REST GATED:
  Free (automatic, no request needed):
    - /stats       National aggregated counts only
    - /heatmap     GPS + verdict + category, no brand/manufacturer names
    - /enforcement Raid candidate queue  their primary enforcement tool

  Gated (NAFDAC must submit a data request, super_admin approves):
    - /trends      Time series data
    - /markets     Location cluster intelligence
    - /categories  Category-level fake rate breakdown

  Permanently blocked (never available to NAFDAC):
    - /products    Reveals brand/manufacturer  company proprietary
    - /recent-scans Individual scan records  too granular

REQUEST FLOW:
  1. NAFDAC hits a gated endpoint : receives 202 with request_required=True
  2. NAFDAC submits POST /api/dashboard/request with purpose
  3. super_admin sees pending request in GET /api/dashboard/requests
  4. super_admin approves/denies via PATCH /api/dashboard/requests/{id}
  5. Approved NAFDAC user can now access that endpoint for 30 days

SECURITY:
  company_id is ALWAYS from the JWT  never from request body or URL params.
  Data request approvals are time-limited (30 days by default).
  All approvals are logged with reviewer identity and timestamp.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, AsyncSessionLocal
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.utils.response import success_response, error_response

logger = logging.getLogger("dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


#  Role helpers 

def _is_admin(user: User) -> bool:
    return str(user.role) == "super_admin"

def _is_nafdac(user: User) -> bool:
    return str(user.role) in ("nafdac_admin", "nafdac_officer")

def _is_company(user: User) -> bool:
    return str(user.role) == "company_admin"

def _can_access_dashboard(user: User) -> bool:
    return _is_admin(user) or _is_nafdac(user) or _is_company(user)

def _company_filter(user: User) -> Optional[str]:
    if _is_company(user) and user.company_id:
        return str(user.company_id)
    return None

def _date_range(days: int):
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


#  NAFDAC gated access check ─

GATED_ENDPOINTS = ("trends", "markets", "categories")

async def _check_nafdac_access(
    user: User,
    endpoint: str,
    db: AsyncSession,
) -> bool:
    """
    Check whether a NAFDAC user has an approved, unexpired data request
    for the given endpoint.

    Returns True if access is granted.
    Raises HTTPException(202) if access requires a request.
    """
    if not _is_nafdac(user):
        return True  # Non-NAFDAC users bypass this check

    if endpoint not in GATED_ENDPOINTS:
        return True  # Not a gated endpoint

    # Check for an approved, unexpired request
    result = await db.execute(text("""
        SELECT id, expires_at
        FROM data_requests
        WHERE user_id  = :user_id
          AND endpoint = :endpoint
          AND status   = 'approved'
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY approved_at DESC
        LIMIT 1
    """), {"user_id": str(user.id), "endpoint": endpoint})

    row = result.fetchone()
    if row:
        return True

    # No approved request  return 202 with instructions
    # Frontend should show "Request Access" button instead of error
    raise HTTPException(
        status_code=202,
        detail={
            "request_required": True,
            "endpoint":         endpoint,
            "message": (
                f"Access to '{endpoint}' data requires a data request. "
                f"Submit a request at POST /api/dashboard/request explaining "
                f"why you need this data. A SabiLens admin will review and approve it."
            ),
            "request_url": "/api/dashboard/request",
        }
    )


#  1. Stats (FREE for NAFDAC) 

@router.get("/stats")
async def get_dashboard_stats(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Summary statistics  FREE for all dashboard roles including NAFDAC.

    Admin:   Full system stats.
    Company: Own products only.
    NAFDAC:  National aggregated counts. No company breakdown. No user counts.
    """
    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access requires admin, NAFDAC, or company role")

    company_id = _company_filter(current_user)
    start, end = _date_range(days)
    prev_start = start - timedelta(days=days)

    company_clause = "AND u.company_id = :company_id" if company_id else ""
    params = {"start": start, "end": end}
    if company_id:
        params["company_id"] = company_id

    try:
        result = await db.execute(text(f"""
            SELECT
                COUNT(*)                                                     AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')       AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')      AS suspicious_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')            AS fake_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'RESCAN_REQUIRED') AS rescan_count,
                COUNT(DISTINCT s.user_id)                                   AS unique_users,
                COUNT(DISTINCT s.nafdac_number)                             AS unique_products
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at BETWEEN :start AND :end
            {company_clause}
        """), params)
        row = result.fetchone()

        total      = int(row.total_scans    or 0)
        authentic  = int(row.authentic_count or 0)
        suspicious = int(row.suspicious_count or 0)
        fake       = int(row.fake_count     or 0)
        rescan     = int(row.rescan_count   or 0)
        fake_rate  = round(fake / total * 100, 1) if total > 0 else 0.0

        prev_params = {**params, "start": prev_start, "end": start}
        prev_result = await db.execute(text(f"""
            SELECT COUNT(*) AS total_scans,
                   COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE') AS fake_count
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at BETWEEN :start AND :end
            {company_clause}
        """), prev_params)
        prev       = prev_result.fetchone()
        prev_total = int(prev.total_scans or 0)
        prev_fake  = int(prev.fake_count  or 0)

        scan_trend = round((total - prev_total) / prev_total * 100, 1) if prev_total > 0 else 0.0
        fake_trend = round((fake  - prev_fake)  / prev_fake  * 100, 1) if prev_fake  > 0 else 0.0

        data = {
            "period_days":      days,
            "total_scans":      total,
            "authentic_count":  authentic,
            "suspicious_count": suspicious,
            "fake_count":       fake,
            "rescan_count":     rescan,
            "fake_rate_pct":    fake_rate,
            "unique_products":  int(row.unique_products or 0),
            "trends": {
                "scan_change_pct": scan_trend,
                "fake_change_pct": fake_trend,
                "direction": "up" if fake_trend > 0 else "down" if fake_trend < 0 else "flat",
            },
        }

        if _is_admin(current_user):
            data["unique_users"] = int(row.unique_users or 0)

        return success_response(data=data, message="Dashboard statistics retrieved")

    except Exception as exc:
        logger.exception("Dashboard stats failed: %s", exc)
        return error_response(str(exc), code="STATS_ERROR", status_code=500)


#  2. Heatmap (FREE for NAFDAC) 

@router.get("/heatmap")
async def get_heatmap(
    days:    int = Query(default=30, ge=1, le=365),
    verdict: str = Query(default="all", description="all | AUTHENTIC | SUSPICIOUS | FAKE"),
    limit:   int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GPS scan points for map heatmap  FREE for NAFDAC.

    NAFDAC receives GPS + verdict + category only.
    Product name and manufacturer are withheld to protect brand client confidentiality.
    """
    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    company_id     = _company_filter(current_user)
    start, _       = _date_range(days)
    verdict_clause = "AND UPPER(s.status) = :verdict" if verdict.upper() != "ALL" else ""
    company_clause = "AND u.company_id = :company_id" if company_id else ""
    params         = {"start": start, "limit": limit}
    if verdict.upper() != "ALL":
        params["verdict"] = verdict.upper()
    if company_id:
        params["company_id"] = company_id

    try:
        result = await db.execute(text(f"""
            SELECT s.id, s.latitude, s.longitude, s.status AS verdict,
                   s.product_name, s.nafdac_number, s.manufacturer,
                   s.category, s.created_at, s.confidence_score
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at >= :start
              AND s.latitude  IS NOT NULL
              AND s.longitude IS NOT NULL
              {verdict_clause}
              {company_clause}
            ORDER BY s.created_at DESC
            LIMIT :limit
        """), params)

        rows = result.fetchall()

        if _is_nafdac(current_user):
            # NAFDAC: location + verdict + category only  no brand identity
            points = [{
                "id":             str(r.id),
                "lat":            float(r.latitude),
                "lng":            float(r.longitude),
                "verdict":        (r.verdict or "UNKNOWN").upper(),
                "category":       r.category,
                "confidence_pct": round(float(r.confidence_score or 0) * 100, 1),
                "scanned_at":     r.created_at.isoformat() if r.created_at else None,
            } for r in rows]
        else:
            # Admin and company: full detail
            points = [{
                "id":             str(r.id),
                "lat":            float(r.latitude),
                "lng":            float(r.longitude),
                "verdict":        (r.verdict or "UNKNOWN").upper(),
                "product_name":   r.product_name,
                "nafdac_number":  r.nafdac_number,
                "manufacturer":   r.manufacturer,
                "category":       r.category,
                "confidence_pct": round(float(r.confidence_score or 0) * 100, 1),
                "scanned_at":     r.created_at.isoformat() if r.created_at else None,
            } for r in rows]

        return success_response(data={
            "points":         points,
            "total":          len(points),
            "verdict_colors": {
                "AUTHENTIC":  "#1A7A4A",
                "SUSPICIOUS": "#C8960C",
                "FAKE":       "#C0392B",
                "UNKNOWN":    "#888888",
            },
            "period_days": days,
            "data_policy": "anonymised" if _is_nafdac(current_user) else "full",
        }, message="Heatmap data retrieved")

    except Exception as exc:
        logger.exception("Heatmap failed: %s", exc)
        return error_response(str(exc), code="HEATMAP_ERROR", status_code=500)


#  3. Products (admin/company only  permanently blocked for NAFDAC) ─

@router.get("/products")
async def get_product_breakdown(
    days:  int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Per-product verdict breakdown  admin and company only.
    Permanently blocked for NAFDAC (reveals brand/manufacturer identity).
    """
    if _is_nafdac(current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "blocked":  True,
                "reason":   "Product breakdown contains company-confidential brand and manufacturer data.",
                "guidance": "Use /api/dashboard/categories for category-level intelligence or /api/dashboard/enforcement for raid intelligence.",
            }
        )

    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    company_id     = _company_filter(current_user)
    start, _       = _date_range(days)
    company_clause = "AND u.company_id = :company_id" if company_id else ""
    params         = {"start": start, "limit": limit}
    if company_id:
        params["company_id"] = company_id

    try:
        result = await db.execute(text(f"""
            SELECT
                COALESCE(s.product_name, s.nafdac_number, 'Unknown Product') AS product_name,
                s.nafdac_number, s.manufacturer, s.category,
                COUNT(*)                                                      AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')        AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')       AS suspicious_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')             AS fake_count,
                ROUND(COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1)                          AS fake_rate_pct,
                MAX(s.created_at)                                             AS last_scanned_at,
                AVG(s.confidence_score)                                       AS avg_confidence
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at >= :start
              AND (s.product_name IS NOT NULL OR s.nafdac_number IS NOT NULL)
              {company_clause}
            GROUP BY s.product_name, s.nafdac_number, s.manufacturer, s.category
            ORDER BY fake_count DESC, total_scans DESC
            LIMIT :limit
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "products": [{
                "product_name":    r.product_name,
                "nafdac_number":   r.nafdac_number,
                "manufacturer":    r.manufacturer,
                "category":        r.category,
                "total_scans":     int(r.total_scans),
                "authentic_count": int(r.authentic_count  or 0),
                "suspicious_count":int(r.suspicious_count or 0),
                "fake_count":      int(r.fake_count       or 0),
                "fake_rate_pct":   float(r.fake_rate_pct  or 0),
                "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
                "avg_confidence":  round(float(r.avg_confidence or 0), 4),
            } for r in rows],
            "total":       len(rows),
            "period_days": days,
        }, message="Product breakdown retrieved")

    except Exception as exc:
        logger.exception("Product breakdown failed: %s", exc)
        return error_response(str(exc), code="PRODUCTS_ERROR", status_code=500)


#  4. Trends (GATED for NAFDAC) 

@router.get("/trends")
async def get_trends(
    days:        int = Query(default=30, ge=7,  le=365),
    granularity: str = Query(default="daily", description="daily | weekly | monthly"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verdict counts over time  GATED for NAFDAC (requires approved data request).
    """
    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    # NAFDAC must have an approved request to access trends
    await _check_nafdac_access(current_user, "trends", db)

    company_id     = _company_filter(current_user)
    start, end     = _date_range(days)
    company_clause = "AND u.company_id = :company_id" if company_id else ""
    params         = {"start": start, "end": end}
    if company_id:
        params["company_id"] = company_id

    trunc = {"daily": "day", "weekly": "week", "monthly": "month"}.get(granularity, "day")

    try:
        result = await db.execute(text(f"""
            SELECT
                DATE_TRUNC('{trunc}', s.created_at)                      AS period,
                COUNT(*)                                                  AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')    AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')   AS suspicious_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')         AS fake_count
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at BETWEEN :start AND :end
              {company_clause}
            GROUP BY DATE_TRUNC('{trunc}', s.created_at)
            ORDER BY period ASC
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "series": [{
                "period":          r.period.isoformat() if r.period else None,
                "total_scans":     int(r.total_scans),
                "authentic_count": int(r.authentic_count  or 0),
                "suspicious_count":int(r.suspicious_count or 0),
                "fake_count":      int(r.fake_count       or 0),
                "fake_rate_pct":   round(
                    int(r.fake_count or 0) / int(r.total_scans) * 100, 1
                ) if int(r.total_scans) > 0 else 0.0,
            } for r in rows],
            "granularity": granularity,
            "period_days": days,
        }, message="Trend data retrieved")

    except Exception as exc:
        logger.exception("Trends failed: %s", exc)
        return error_response(str(exc), code="TRENDS_ERROR", status_code=500)


#  5. Markets (GATED for NAFDAC) ─

@router.get("/markets")
async def get_markets(
    days:  int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Top scan locations by fake concentration  GATED for NAFDAC.
    """
    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    await _check_nafdac_access(current_user, "markets", db)

    company_id     = _company_filter(current_user)
    start, _       = _date_range(days)
    params         = {"start": start, "limit": limit}

    if _is_nafdac(current_user):
        # NAFDAC query: no company join, no brand names
        query = """
            SELECT
                ROUND(s.latitude::numeric,  2) AS cluster_lat,
                ROUND(s.longitude::numeric, 2) AS cluster_lng,
                s.location_text,
                COUNT(*)                                                  AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')        AS fake_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')   AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')  AS suspicious_count,
                ROUND(COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1)                     AS fake_rate_pct,
                MAX(s.created_at)                                        AS last_scan_at,
                array_agg(DISTINCT s.category)
                    FILTER (WHERE s.category IS NOT NULL)                AS categories_affected
            FROM scans s
            WHERE s.created_at >= :start
              AND s.latitude  IS NOT NULL
              AND s.longitude IS NOT NULL
            GROUP BY ROUND(s.latitude::numeric,2), ROUND(s.longitude::numeric,2), s.location_text
            ORDER BY fake_count DESC, total_scans DESC
            LIMIT :limit
        """
    else:
        company_clause = "AND u.company_id = :company_id" if company_id else ""
        if company_id:
            params["company_id"] = company_id
        query = f"""
            SELECT
                ROUND(s.latitude::numeric,  2) AS cluster_lat,
                ROUND(s.longitude::numeric, 2) AS cluster_lng,
                s.location_text,
                COUNT(*)                                                  AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')        AS fake_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')   AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')  AS suspicious_count,
                ROUND(COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1)                     AS fake_rate_pct,
                MAX(s.created_at)                                        AS last_scan_at,
                array_agg(DISTINCT s.category)
                    FILTER (WHERE s.category IS NOT NULL)                AS categories_affected
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at >= :start
              AND s.latitude  IS NOT NULL
              AND s.longitude IS NOT NULL
              {company_clause}
            GROUP BY ROUND(s.latitude::numeric,2), ROUND(s.longitude::numeric,2), s.location_text
            ORDER BY fake_count DESC, total_scans DESC
            LIMIT :limit
        """

    try:
        result = await db.execute(text(query), params)
        rows   = result.fetchall()
        return success_response(data={
            "markets": [{
                "cluster_lat":        float(r.cluster_lat),
                "cluster_lng":        float(r.cluster_lng),
                "location_text":      r.location_text,
                "total_scans":        int(r.total_scans),
                "fake_count":         int(r.fake_count       or 0),
                "authentic_count":    int(r.authentic_count  or 0),
                "suspicious_count":   int(r.suspicious_count or 0),
                "fake_rate_pct":      float(r.fake_rate_pct  or 0),
                "last_scan_at":       r.last_scan_at.isoformat() if r.last_scan_at else None,
                "categories_affected":getattr(r, "categories_affected", None) or [],
                "risk_level": (
                    "HIGH"   if float(r.fake_rate_pct or 0) >= 40 else
                    "MEDIUM" if float(r.fake_rate_pct or 0) >= 20 else
                    "LOW"
                ),
            } for r in rows],
            "total":       len(rows),
            "period_days": days,
            "data_policy": "anonymised" if _is_nafdac(current_user) else "full",
        }, message="Market intelligence retrieved")

    except Exception as exc:
        logger.exception("Markets failed: %s", exc)
        return error_response(str(exc), code="MARKETS_ERROR", status_code=500)


#  6. Enforcement (FREE for NAFDAC) ─

@router.get("/enforcement")
async def get_enforcement_queue(
    days:  int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    NAFDAC enforcement case queue  FREE for NAFDAC.
    Returns GPS clusters with 3+ FAKE verdicts = IMMEDIATE_RAID_CANDIDATE.
    Company users are blocked  enforcement covers all brands.
    """
    if not (_is_admin(current_user) or _is_nafdac(current_user)):
        raise HTTPException(
            status_code=403,
            detail="Enforcement queue requires NAFDAC officer or super_admin role"
        )

    start, _ = _date_range(days)
    params   = {"start": start, "limit": limit}

    try:
        result = await db.execute(text("""
            SELECT
                ROUND(s.latitude::numeric,  2)  AS cluster_lat,
                ROUND(s.longitude::numeric, 2)  AS cluster_lng,
                s.location_text,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')   AS fake_count,
                COUNT(*)                                            AS total_scans,
                array_agg(DISTINCT s.category)
                    FILTER (WHERE s.category IS NOT NULL)           AS categories_affected,
                array_agg(DISTINCT s.nafdac_number)
                    FILTER (WHERE s.nafdac_number IS NOT NULL)      AS nafdac_numbers,
                MIN(s.created_at)                                   AS first_report_at,
                MAX(s.created_at)                                   AS latest_report_at
            FROM scans s
            WHERE s.created_at >= :start
              AND s.latitude  IS NOT NULL
              AND s.longitude IS NOT NULL
            GROUP BY
                ROUND(s.latitude::numeric,  2),
                ROUND(s.longitude::numeric, 2),
                s.location_text
            HAVING COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE') >= 3
            ORDER BY fake_count DESC
            LIMIT :limit
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "cases": [{
                "case_id":            str(uuid.uuid4()),
                "cluster_lat":        float(r.cluster_lat),
                "cluster_lng":        float(r.cluster_lng),
                "location_text":      r.location_text,
                "fake_count":         int(r.fake_count),
                "total_scans":        int(r.total_scans),
                "categories_affected":r.categories_affected or [],
                "nafdac_numbers":     r.nafdac_numbers      or [],
                "first_report_at":    r.first_report_at.isoformat()  if r.first_report_at  else None,
                "latest_report_at":   r.latest_report_at.isoformat() if r.latest_report_at else None,
                "enforcement_action": "IMMEDIATE_RAID_CANDIDATE",
                "priority": (
                    "P1_CRITICAL" if int(r.fake_count) >= 10 else
                    "P2_HIGH"     if int(r.fake_count) >= 5  else
                    "P3_MEDIUM"
                ),
            } for r in rows],
            "total":       len(rows),
            "period_days": days,
            "threshold":   "3+ FAKE verdicts within ~1km radius",
        }, message="Enforcement queue retrieved")

    except Exception as exc:
        logger.exception("Enforcement queue failed: %s", exc)
        return error_response(str(exc), code="ENFORCEMENT_ERROR", status_code=500)


#  7. Recent Scans (permanently blocked for NAFDAC) ─

@router.get("/recent-scans")
async def get_recent_scans(
    limit:   int = Query(default=20, ge=1, le=100),
    verdict: str = Query(default="all", description="all | AUTHENTIC | SUSPICIOUS | FAKE"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Live feed of most recent scans  admin and company only.
    Permanently blocked for NAFDAC  individual records are too granular.
    """
    if _is_nafdac(current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "blocked":  True,
                "reason":   "Individual scan records are not available to NAFDAC.",
                "guidance": "Use /api/dashboard/enforcement for enforcement intelligence.",
            }
        )

    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    company_id     = _company_filter(current_user)
    verdict_clause = "AND UPPER(s.status) = :verdict" if verdict.upper() != "ALL" else ""
    company_clause = "AND u.company_id = :company_id" if company_id else ""
    params         = {"limit": limit}
    if verdict.upper() != "ALL":
        params["verdict"] = verdict.upper()
    if company_id:
        params["company_id"] = company_id

    try:
        result = await db.execute(text(f"""
            SELECT s.id, s.status AS verdict, s.product_name, s.nafdac_number,
                   s.manufacturer, s.category, s.confidence_score,
                   s.latitude, s.longitude, s.location_text, s.image_url, s.created_at
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE 1=1 {verdict_clause} {company_clause}
            ORDER BY s.created_at DESC
            LIMIT :limit
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "scans": [{
                "id":             str(r.id),
                "verdict":        (r.verdict or "UNKNOWN").upper(),
                "product_name":   r.product_name,
                "nafdac_number":  r.nafdac_number,
                "manufacturer":   r.manufacturer,
                "category":       r.category,
                "confidence_pct": round(float(r.confidence_score or 0) * 100, 1),
                "latitude":       float(r.latitude)  if r.latitude  else None,
                "longitude":      float(r.longitude) if r.longitude else None,
                "location_text":  r.location_text,
                "image_url":      r.image_url,
                "scanned_at":     r.created_at.isoformat() if r.created_at else None,
            } for r in rows],
            "total": len(rows),
        }, message="Recent scans retrieved")

    except Exception as exc:
        logger.exception("Recent scans failed: %s", exc)
        return error_response(str(exc), code="RECENT_SCANS_ERROR", status_code=500)


#  8. Categories (GATED for NAFDAC) ─

@router.get("/categories")
async def get_category_intelligence(
    days:  int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Category-level fake rate breakdown  GATED for NAFDAC.
    The NAFDAC-friendly alternative to /products.
    Shows which categories are at risk without revealing brand identity.
    """
    if not _can_access_dashboard(current_user):
        raise HTTPException(status_code=403, detail="Dashboard access required")

    await _check_nafdac_access(current_user, "categories", db)

    company_id     = _company_filter(current_user)
    start, _       = _date_range(days)
    company_clause = "AND u.company_id = :company_id" if (company_id and not _is_nafdac(current_user)) else ""
    params         = {"start": start}
    if company_id and not _is_nafdac(current_user):
        params["company_id"] = company_id

    try:
        result = await db.execute(text(f"""
            SELECT
                COALESCE(s.category, 'Uncategorised') AS category,
                COUNT(*)                                                     AS total_scans,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'AUTHENTIC')       AS authentic_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'SUSPICIOUS')      AS suspicious_count,
                COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')            AS fake_count,
                ROUND(COUNT(*) FILTER (WHERE UPPER(s.status) = 'FAKE')::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1)                         AS fake_rate_pct,
                MAX(s.created_at)                                            AS last_scanned_at
            FROM scans s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.created_at >= :start
              {company_clause}
            GROUP BY COALESCE(s.category, 'Uncategorised')
            ORDER BY fake_count DESC, total_scans DESC
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "categories": [{
                "category":        r.category,
                "total_scans":     int(r.total_scans),
                "authentic_count": int(r.authentic_count  or 0),
                "suspicious_count":int(r.suspicious_count or 0),
                "fake_count":      int(r.fake_count       or 0),
                "fake_rate_pct":   float(r.fake_rate_pct  or 0),
                "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
                "risk_level": (
                    "HIGH"   if float(r.fake_rate_pct or 0) >= 40 else
                    "MEDIUM" if float(r.fake_rate_pct or 0) >= 20 else
                    "LOW"
                ),
            } for r in rows],
            "total":       len(rows),
            "period_days": days,
        }, message="Category intelligence retrieved")

    except Exception as exc:
        logger.exception("Category intelligence failed: %s", exc)
        return error_response(str(exc), code="CATEGORIES_ERROR", status_code=500)



# DATA REQUEST FLOW

class DataRequestCreate(BaseModel):
    endpoint: str
    purpose:  str


class DataRequestReview(BaseModel):
    status:      str   # approved | denied
    review_note: Optional[str] = None
    expires_days: int = 30


#  Submit a data request (NAFDAC) 

@router.post("/request")
async def submit_data_request(
    body: DataRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a data access request for a gated endpoint.
    Available to NAFDAC users only.
    super_admin reviews and approves/denies via PATCH /api/dashboard/requests/{id}
    """
    if not _is_nafdac(current_user):
        raise HTTPException(status_code=403, detail="Data requests are for NAFDAC users only")

    if body.endpoint not in GATED_ENDPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"'{body.endpoint}' is not a gated endpoint. Gated endpoints: {list(GATED_ENDPOINTS)}"
        )

    if not body.purpose or len(body.purpose.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Please provide a detailed purpose (minimum 20 characters) explaining why you need this data."
        )

    try:
        request_id = str(uuid.uuid4())
        await db.execute(text("""
            INSERT INTO data_requests
                (id, user_id, endpoint, purpose, status, created_at)
            VALUES
                (:id, :user_id, :endpoint, :purpose, 'pending', NOW())
        """), {
            "id":       request_id,
            "user_id":  str(current_user.id),
            "endpoint": body.endpoint,
            "purpose":  body.purpose.strip(),
        })
        await db.commit()

        logger.info(
            "Data request submitted | id=%s | user=%s | endpoint=%s",
            request_id, current_user.id, body.endpoint,
        )

        return success_response(data={
            "request_id": request_id,
            "endpoint":   body.endpoint,
            "status":     "pending",
            "message":    "Your request has been submitted. A SabiLens admin will review it and you will be notified.",
        }, message="Data request submitted successfully")

    except Exception as exc:
        logger.exception("Data request submission failed: %s", exc)
        return error_response(str(exc), code="REQUEST_ERROR", status_code=500)


#  List pending requests (super_admin only) 

@router.get("/requests")
async def list_data_requests(
    status: str = Query(default="pending", description="pending | approved | denied | all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List data access requests for review.
    super_admin only  this is the admin's approval queue.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Request review requires super_admin role")

    status_clause = "AND dr.status = :status" if status != "all" else ""
    params        = {}
    if status != "all":
        params["status"] = status

    try:
        result = await db.execute(text(f"""
            SELECT
                dr.id, dr.endpoint, dr.purpose, dr.status,
                dr.review_note, dr.approved_at, dr.expires_at, dr.created_at,
                u.first_name, u.last_name, u.email, u.phone, u.role
            FROM data_requests dr
            JOIN users u ON u.id = dr.user_id
            WHERE 1=1 {status_clause}
            ORDER BY dr.created_at DESC
        """), params)

        rows = result.fetchall()
        return success_response(data={
            "requests": [{
                "id":           str(r.id),
                "endpoint":     r.endpoint,
                "purpose":      r.purpose,
                "status":       r.status,
                "review_note":  r.review_note,
                "approved_at":  r.approved_at.isoformat()  if r.approved_at  else None,
                "expires_at":   r.expires_at.isoformat()   if r.expires_at   else None,
                "submitted_at": r.created_at.isoformat()   if r.created_at   else None,
                "requester": {
                    "name":  f"{r.first_name or ''} {r.last_name or ''}".strip() or "Unknown",
                    "email": r.email,
                    "phone": r.phone,
                    "role":  r.role,
                },
            } for r in rows],
            "total": len(rows),
        }, message="Data requests retrieved")

    except Exception as exc:
        logger.exception("List requests failed: %s", exc)
        return error_response(str(exc), code="REQUESTS_ERROR", status_code=500)


#  Approve or deny a request (super_admin only) 

@router.patch("/requests/{request_id}")
async def review_data_request(
    request_id: str,
    body: DataRequestReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve or deny a NAFDAC data access request.
    super_admin only.

    Approved requests grant access to the endpoint for expires_days (default 30).
    Denied requests are logged with the review note.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Request review requires super_admin role")

    if body.status not in ("approved", "denied"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'denied'")

    try:
        # Check request exists
        check = await db.execute(text("""
            SELECT id, status FROM data_requests WHERE id = :id
        """), {"id": request_id})
        row = check.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Data request not found")
        if row.status != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already '{row.status}'")

        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=body.expires_days)
            if body.status == "approved" else None
        )

        await db.execute(text("""
            UPDATE data_requests
            SET status      = :status,
                review_note = :review_note,
                reviewed_by = :reviewed_by,
                approved_at = CASE WHEN :status = 'approved' THEN NOW() ELSE NULL END,
                expires_at  = :expires_at
            WHERE id = :id
        """), {
            "id":          request_id,
            "status":      body.status,
            "review_note": body.review_note,
            "reviewed_by": str(current_user.id),
            "expires_at":  expires_at,
        })
        await db.commit()

        logger.info(
            "Data request %s | id=%s | reviewed_by=%s | expires=%s",
            body.status, request_id, current_user.id, expires_at,
        )

        return success_response(data={
            "request_id":  request_id,
            "status":      body.status,
            "expires_at":  expires_at.isoformat() if expires_at else None,
            "review_note": body.review_note,
        }, message=f"Data request {body.status}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request review failed: %s", exc)
        return error_response(str(exc), code="REVIEW_ERROR", status_code=500)
