"""Scan and report models"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, TEXT, Numeric, Date, Index, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class ScanStatus(str, enum.Enum):
    AUTHENTIC = "authentic"
    CAUTION = "caution"
    FAKE = "fake"
    PENDING = "pending"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PurchaseChannel(str, enum.Enum):
    MARKET_STALL = "market_stall"
    ROADSIDE_VENDOR = "roadside_vendor"
    SUPERMARKET = "supermarket"
    SUPPLIER = "supplier"
    ONLINE = "online"
    OTHER = "other"


class Scan(Base):
    """Scans table"""
    __tablename__ = "scans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), nullable=False)  # FK to users
    product_id = Column(String(36))  # FK to products
    product_name = Column(String(255))
    category = Column(String(100))
    manufacturer = Column(String(255))
    nafdac_number = Column(String(100))
    batch_number = Column(String(100))
    expiry_date = Column(Date)
    status = Column(SQLEnum(ScanStatus))
    similarity_score = Column(Numeric(5, 2))
    confidence_score = Column(Numeric(5, 2))
    scan_image_urls = Column(String)  # Array
    scan_location = Column(String)  # GEOGRAPHY(POINT)
    location_name = Column(String(255))
    scan_metadata = Column(String)  # JSONB
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index("idx_scans_user", "user_id"),
        Index("idx_scans_product", "product_id"),
        Index("idx_scans_status", "status"),
        Index("idx_scans_created", "created_at"),
    )


class ScanAnalysis(Base):
    """Scan analysis results (detailed AI output)"""
    __tablename__ = "scan_analyses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scan_id = Column(String(36), nullable=False)  # FK to scans
    ai_model_version = Column(String(50))
    features_detected = Column(String)  # JSONB
    anomalies = Column(String)  # JSONB
    ocr_text = Column(TEXT)
    visual_fingerprint = Column(String)  # JSONB
    analysis_time_ms = Column(None)  # Integer
    created_at = Column(DateTime, default=func.now())


class Report(Base):
    """Counterfeit reports table"""
    __tablename__ = "reports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scan_id = Column(String(36), nullable=False)  # FK to scans
    user_id = Column(String(36), nullable=False)  # FK to users
    product_id = Column(String(36))  # FK to products
    company_id = Column(String(36))  # FK to companies
    report_status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    severity = Column(SQLEnum(Severity))
    purchase_channel = Column(SQLEnum(PurchaseChannel))
    purchase_channel_details = Column(TEXT)
    price_paid = Column(Numeric(10, 2))
    receipt_image_urls = Column(String)  # Array
    additional_comments = Column(TEXT)
    gps_location = Column(String)  # GEOGRAPHY(POINT)
    location_name = Column(String(255))
    reported_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36))  # FK to users
    resolution_notes = Column(TEXT)
    
    __table_args__ = (
        Index("idx_reports_scan", "scan_id"),
        Index("idx_reports_company", "company_id"),
        Index("idx_reports_status", "report_status"),
        Index("idx_reports_severity", "severity"),
    )


class ReportEvidence(Base):
    """Report evidence table"""
    __tablename__ = "report_evidence"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_id = Column(String(36), nullable=False)  # FK to reports
    evidence_type = Column(String(50))  # image, video, receipt, document
    file_url = Column(TEXT, nullable=False)
    file_size = Column(None)  # Integer
    mime_type = Column(String(100))
    uploaded_by = Column(String(36))  # FK to users
    created_at = Column(DateTime, default=func.now())
