"""Geospatial and analytics models."""
import uuid
from sqlalchemy import (
    Column, String, Integer, Date, DateTime, ForeignKey,
    Numeric, Boolean, Text, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base

# NOTE: geoalchemy2 is required for Geography columns.
# Install with: pip install geoalchemy2
# Fallback lat/lng columns are provided if geoalchemy2 is unavailable.
try:
    from geoalchemy2 import Geography
    _USE_GEOGRAPHY = True
except ImportError:
    _USE_GEOGRAPHY = False


class AnalyticsDaily(Base):
    """Daily analytics aggregates.

    Scope axes (all nullable):
      company_id IS NULL, state IS NULL  → platform-wide aggregate
      company_id = X                     → per-company daily shard
      state      = Y                     → per-state daily shard

    Unique key: (date, company_id, state) — enforced by uix_analytics_daily_scope.
    """
    __tablename__ = "analytics_daily"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)             # unique=True removed — composite index handles uniqueness
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    state = Column(String(100), nullable=True)
    total_scans = Column(Integer, default=0)
    authentic_scans = Column(Integer, default=0)
    suspicious_scans = Column(Integer, default=0)
    counterfeit_scans = Column(Integer, default=0)
    total_reports = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    unique_companies = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class AnalyticsCategory(Base):
    """Category analytics."""
    __tablename__ = "analytics_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    category_name = Column(String(100), nullable=True)
    period = Column(String(20), nullable=True)
    # CHECK: period IN ('daily', 'weekly', 'monthly', 'quarterly')
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    scan_count = Column(Integer, default=0)
    counterfeit_count = Column(Integer, default=0)
    suspicious_count = Column(Integer, default=0)
    authentic_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class AnalyticsRegion(Base):
    """Regional analytics."""
    __tablename__ = "analytics_regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state = Column(String(100), nullable=False)
    city = Column(String(100), nullable=True)
    period = Column(String(20), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    scan_count = Column(Integer, default=0)
    counterfeit_count = Column(Integer, default=0)
    risk_score = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


if _USE_GEOGRAPHY:
    class Hotspot(Base):
        """Counterfeit hotspots (PostGIS Geography)."""
        __tablename__ = "hotspots"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
        region_name = Column(String(255), nullable=True)
        city = Column(String(100), nullable=True)
        state = Column(String(100), nullable=True)
        country = Column(String(100), default="Nigeria")
        report_count = Column(Integer, default=0)
        severity_score = Column(Numeric(5, 2), nullable=True)
        risk_level = Column(String(50), nullable=True)
        # CHECK: risk_level IN ('critical', 'high', 'medium', 'low')
        last_updated = Column(DateTime, server_default=func.now())
        created_at = Column(DateTime, server_default=func.now())

    class VendorLocation(Base):
        """Vendor locations (where counterfeits were purchased) — PostGIS Geography."""
        __tablename__ = "vendor_locations"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
        vendor_name = Column(String(255), nullable=True)
        location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
        address = Column(Text, nullable=True)
        city = Column(String(100), nullable=True)
        state = Column(String(100), nullable=True)
        report_count = Column(Integer, default=1)
        risk_level = Column(String(50), default="unknown")
        # CHECK: risk_level IN ('critical', 'high', 'medium', 'low', 'unknown')
        is_blacklisted = Column(Boolean, default=False)
        blacklisted_at = Column(DateTime, nullable=True)
        blacklisted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
        last_reported_at = Column(DateTime, nullable=True)
        created_at = Column(DateTime, server_default=func.now())

else:
    # Fallback: store lat/lng as numeric columns instead of PostGIS Geography
    class Hotspot(Base):
        """Counterfeit hotspots (lat/lng fallback)."""
        __tablename__ = "hotspots"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        location_lat = Column(Numeric(10, 7), nullable=True)
        location_lng = Column(Numeric(10, 7), nullable=True)
        region_name = Column(String(255), nullable=True)
        city = Column(String(100), nullable=True)
        state = Column(String(100), nullable=True)
        country = Column(String(100), default="Nigeria")
        report_count = Column(Integer, default=0)
        severity_score = Column(Numeric(5, 2), nullable=True)
        risk_level = Column(String(50), nullable=True)
        last_updated = Column(DateTime, server_default=func.now())
        created_at = Column(DateTime, server_default=func.now())

    class VendorLocation(Base):
        """Vendor locations (lat/lng fallback)."""
        __tablename__ = "vendor_locations"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
        vendor_name = Column(String(255), nullable=True)
        location_lat = Column(Numeric(10, 7), nullable=True)
        location_lng = Column(Numeric(10, 7), nullable=True)
        address = Column(Text, nullable=True)
        city = Column(String(100), nullable=True)
        state = Column(String(100), nullable=True)
        report_count = Column(Integer, default=1)
        risk_level = Column(String(50), default="unknown")
        is_blacklisted = Column(Boolean, default=False)
        blacklisted_at = Column(DateTime, nullable=True)
        blacklisted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
        last_reported_at = Column(DateTime, nullable=True)
        created_at = Column(DateTime, server_default=func.now())


class NigerianState(Base):
    """Nigerian states lookup table."""
    __tablename__ = "nigerian_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    capital = Column(String(100), nullable=True)
    region = Column(String(50), nullable=True)


class Language(Base):
    """Languages lookup table."""
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)


class AuditLog(Base):
    """Audit logs (for compliance)."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)  # INET type stored as string
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SystemLog(Base):
    """System logs."""
    __tablename__ = "system_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    log_level = Column(String(20), nullable=True)
    # CHECK: log_level IN ('debug', 'info', 'warning', 'error', 'critical')
    component = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
