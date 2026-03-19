"""Report related models — owned by Mr Openx."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Numeric, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Report(Base):
    """Counterfeit reports table."""
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    report_status = Column(String(50), default="pending")
    # status IN ('pending', 'verified', 'investigating', 'resolved', 'rejected')
    severity = Column(String(50), nullable=True)
    # severity IN ('critical', 'high', 'medium', 'low')
    purchase_channel = Column(String(100), nullable=True)
    # purchase_channel IN ('market_stall', 'roadside_vendor', 'supermarket', 'supplier', 'online', 'other')
    purchase_channel_details = Column(Text, nullable=True)
    price_paid = Column(Numeric(12, 2), nullable=True)
    receipt_image_urls = Column(JSONB, nullable=True)
    additional_comments = Column(Text, nullable=True)
    gps_location = Column(String, nullable=True)  # GEOGRAPHY(POINT) or lat/lng string
    location_name = Column(String(255), nullable=True)
    reported_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)


class ReportEvidence(Base):
    """Report evidence table."""
    __tablename__ = "report_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    evidence_type = Column(String(50), nullable=True)  # image, video, receipt, document
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
