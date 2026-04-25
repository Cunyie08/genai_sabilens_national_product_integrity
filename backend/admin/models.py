"""Admin ORM models — EnforcementCase and AdminReport."""
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Boolean, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class EnforcementCase(Base):
    __tablename__ = "enforcement_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_key = Column(String(255), nullable=False, unique=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    scan_location_state = Column(String(100), nullable=True)
    scan_location_lga = Column(String(100), nullable=True)
    market_name = Column(String(255), nullable=True)
    center_latitude = Column(Float, nullable=True)
    center_longitude = Column(Float, nullable=True)
    fake_scan_count = Column(Integer, nullable=False, default=0)
    suspicious_scan_count = Column(Integer, nullable=False, default=0)
    total_scan_count = Column(Integer, nullable=False, default=0)
    risk_score = Column(Float, nullable=False, default=0.0)
    # status IN ('open', 'assigned', 'raid_completed', 'prosecuted', 'closed')
    status = Column(String(50), nullable=False, default="open")
    assigned_officer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    evidence_package = Column(JSONB, nullable=True)
    nafdac_case_ref = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AdminReport(Base):
    __tablename__ = "admin_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # report_type IN ('scan_analysis', 'product_intelligence', 'market_summary', 'company_overview')
    report_type = Column(String(100), nullable=False)
    filter_state = Column(String(100), nullable=True)
    filter_lga = Column(String(100), nullable=True)
    filter_subcategory_id = Column(UUID(as_uuid=True), nullable=True)
    filter_date_from = Column(Date, nullable=True)
    filter_date_to = Column(Date, nullable=True)
    task_id = Column(String(255), nullable=True)
    # status IN ('queued', 'processing', 'ready', 'failed')
    status = Column(String(50), nullable=False, default="queued")
    gcs_key = Column(Text, nullable=True)
    report_json = Column(JSONB, nullable=True)
    signed_url = Column(Text, nullable=True)
    signed_url_expires_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
