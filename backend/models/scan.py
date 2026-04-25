"""Scan models."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Float, Date, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Scan(Base):
    """Scans table."""
    __tablename__ = "scans"

    # Columns from migration 001 (already in Supabase)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    image_url = Column(String, nullable=True)          # primary (front) scan image URL
    barcode = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)            # real GPS latitude from user device
    longitude = Column(Float, nullable=True)           # real GPS longitude from user device
    location_text = Column(String, nullable=True)      # human-readable address / coordinate string
    status = Column(String(50), nullable=True)
    # status IN ('processing', 'authentic', 'suspicious', 'fake', 'caution', 'pending')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)

    # Columns added for admin dashboard (already exist in GCP — added here for ORM awareness)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    scan_location_state = Column(String(100), nullable=True)
    scan_location_lga = Column(String(100), nullable=True)
    market_name = Column(String(255), nullable=True)
    consumer_id_hash = Column(String(64), nullable=True)  # SHA-256 hash only — never raw ID

    # Columns added by migration 002
    product_name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    nafdac_number = Column(String(100), nullable=True)
    batch_number = Column(String(100), nullable=True)
    expiry_date = Column(Date, nullable=True)
    similarity_score = Column(Numeric(5, 2), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    back_image_url = Column(String, nullable=True)     # back-panel scan image URL
    scan_image_urls = Column(JSONB, nullable=True)     # all image URLs as array
    scan_data = Column(JSONB, nullable=True)           # full AI result payload


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
