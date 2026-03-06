"""
Report model — owned by Mr Openx.
This stub allows imports to resolve. Replace with the real implementation.
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from backend_femi.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    report_status = Column(String(50), default="pending")
    # status IN ('pending', 'verified', 'investigating', 'resolved', 'rejected')
    severity = Column(String(50), nullable=True)
    purchase_channel = Column(String(100), nullable=True)
    price_paid = Column(Numeric(12, 2), nullable=True)
    additional_comments = Column(Text, nullable=True)
    location_name = Column(String(255), nullable=True)
    reported_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
