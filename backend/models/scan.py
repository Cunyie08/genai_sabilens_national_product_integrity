"""Scan models — owned by tunjipaul."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Date, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Scan(Base):
    """Scans table."""
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    nafdac_number = Column(String(100), nullable=True)
    batch_number = Column(String(100), nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(50), nullable=True)
    # status IN ('processing', 'authentic', 'suspicious', 'fake', 'caution', 'pending')
    similarity_score = Column(Numeric(5, 2), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    scan_image_urls = Column(JSONB, nullable=True)
    scan_location = Column(String, nullable=True)  # GEOGRAPHY(POINT) or string
    location_name = Column(String(255), nullable=True)
    scan_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ScanAnalysis(Base):
    """Scan analysis results (detailed AI output)."""
    __tablename__ = "scan_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    ai_model_version = Column(String(50), nullable=True)
    features_detected = Column(JSONB, nullable=True)
    anomalies = Column(JSONB, nullable=True)
    ocr_text = Column(Text, nullable=True)
    visual_fingerprint = Column(JSONB, nullable=True)
    analysis_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
