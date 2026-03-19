from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from enum import Enum


# ─── Enums ───────────────────────────────────────────────

class AlertTypeEnum(str, Enum):
    counterfeit = "counterfeit"
    suspicious = "suspicious"
    bulk = "bulk"
    recurring = "recurring"


class SeverityEnum(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class RiskLevelEnum(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class ReportStatusEnum(str, Enum):
    pending = "pending"
    verified = "verified"
    investigating = "investigating"
    resolved = "resolved"
    rejected = "rejected"


class CompanyStatusEnum(str, Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    rejected = "rejected"


class PeriodEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"


class ExportFormatEnum(str, Enum):
    csv = "csv"
    pdf = "pdf"
    json = "json"


# ─── Officer Schemas ─────────────────────────────────────

class OfficerCreate(BaseModel):
    email: str
    phone: str
    password: str
    first_name: str
    last_name: str
    role: str = "nafdac_officer"  # or "nafdac_admin"


class OfficerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None  # 'active', 'suspended'
    role: Optional[str] = None


class OfficerResponse(BaseModel):
    id: UUID
    email: Optional[str]
    phone: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    status: str
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Company Management Schemas ──────────────────────────

class CompanyListResponse(BaseModel):
    id: UUID
    name: str
    registration_number: str
    email: str
    status: str
    subscription_tier: str
    verified_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyDetailResponse(CompanyListResponse):
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    logo_url: Optional[str] = None
    website: Optional[str] = None


class CompanyVerifyRequest(BaseModel):
    notes: Optional[str] = None


class CompanyRejectRequest(BaseModel):
    reason: str


class CompanyStatsResponse(BaseModel):
    total_companies: int
    active_companies: int
    pending_companies: int
    suspended_companies: int
    rejected_companies: int


# ─── Dashboard Schemas ───────────────────────────────────

class DashboardStatsResponse(BaseModel):
    total_scans: int
    total_reports: int
    total_counterfeit: int
    total_authentic: int
    total_suspicious: int
    active_companies: int
    active_alerts: int
    resolved_cases: int


class DashboardRegionData(BaseModel):
    state: str
    scan_count: int
    counterfeit_count: int
    risk_score: Optional[float]


class DashboardTrendData(BaseModel):
    date: date
    total_scans: int
    counterfeit_scans: int
    authentic_scans: int
    suspicious_scans: int


class LiveAlertResponse(BaseModel):
    id: UUID
    alert_type: Optional[str]
    severity: Optional[str]
    title: str
    message: str
    company_name: Optional[str] = None
    is_acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Alert Schemas ───────────────────────────────────────

class AlertResponse(BaseModel):
    id: UUID
    report_id: Optional[UUID]
    company_id: Optional[UUID]
    alert_type: Optional[str]
    severity: Optional[str]
    title: str
    message: str
    metadata_: Optional[dict] = Field(None, alias="metadata")
    is_read: bool
    is_acknowledged: bool
    acknowledged_by: Optional[UUID]
    acknowledged_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class AlertAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class AlertResolveRequest(BaseModel):
    resolution_notes: str


class BulkAcknowledgeRequest(BaseModel):
    alert_ids: List[UUID]


class AlertStatsResponse(BaseModel):
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    medium_alerts: int
    low_alerts: int
    unacknowledged: int
    acknowledged: int


# ─── Case & Evidence Schemas ─────────────────────────────

class CaseResponse(BaseModel):
    """Maps to the 'reports' table which represents cases in NAFDAC context."""
    id: UUID
    scan_id: UUID
    user_id: UUID
    product_id: Optional[UUID]
    company_id: Optional[UUID]
    report_status: str
    severity: Optional[str]
    purchase_channel: Optional[str]
    price_paid: Optional[float]
    additional_comments: Optional[str]
    location_name: Optional[str]
    reported_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]
    resolution_notes: Optional[str]

    class Config:
        from_attributes = True


class CaseAssignRequest(BaseModel):
    officer_id: UUID
    notes: Optional[str] = None


class CaseStatusUpdateRequest(BaseModel):
    status: ReportStatusEnum
    notes: Optional[str] = None


class CaseSearchParams(BaseModel):
    query: Optional[str] = None
    status: Optional[ReportStatusEnum] = None
    severity: Optional[SeverityEnum] = None
    state: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    limit: int = 20


# ─── Vendor Schemas ──────────────────────────────────────

class VendorResponse(BaseModel):
    id: UUID
    report_id: Optional[UUID]
    vendor_name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    report_count: int
    risk_level: str
    is_blacklisted: bool
    blacklisted_at: Optional[datetime]
    last_reported_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class VendorBlacklistRequest(BaseModel):
    reason: str


class VendorInvestigateRequest(BaseModel):
    notes: str
    priority: Optional[SeverityEnum] = SeverityEnum.medium


class VendorStatsResponse(BaseModel):
    total_vendors: int
    high_risk_vendors: int
    blacklisted_vendors: int
    recurring_offenders: int


# ─── Analytics Schemas ───────────────────────────────────

class AnalyticsFilter(BaseModel):
    period: Optional[PeriodEnum] = PeriodEnum.monthly
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    state: Optional[str] = None
    category_id: Optional[UUID] = None


class CategoryAnalyticsResponse(BaseModel):
    category_name: Optional[str]
    scan_count: int
    counterfeit_count: int
    suspicious_count: int
    authentic_count: int
    period_start: date
    period_end: date

    class Config:
        from_attributes = True


class RegionAnalyticsResponse(BaseModel):
    state: str
    city: Optional[str]
    scan_count: int
    counterfeit_count: int
    risk_score: Optional[float]

    class Config:
        from_attributes = True


class TrendComparisonResponse(BaseModel):
    current_period: List[DashboardTrendData]
    previous_period: List[DashboardTrendData]


class TimelineResponse(BaseModel):
    date: date
    events: int
    scans: int
    reports: int
    alerts: int


class HotspotResponse(BaseModel):
    id: UUID
    latitude: float
    longitude: float
    region_name: Optional[str]
    city: Optional[str]
    state: Optional[str]
    report_count: int
    severity_score: Optional[float]
    risk_level: Optional[str]

    class Config:
        from_attributes = True


class PredictionResponse(BaseModel):
    """Mocked AI prediction data for demo."""
    state: str
    predicted_risk_level: str
    predicted_counterfeit_increase_pct: float
    confidence: float


# ─── Export Schemas ───────────────────────────────────────

class ExportRequest(BaseModel):
    format: ExportFormatEnum = ExportFormatEnum.csv
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    filters: Optional[dict] = None


class ExportResponse(BaseModel):
    export_id: UUID
    status: str  # 'queued', 'processing', 'completed', 'failed'
    file_url: Optional[str] = None
    created_at: datetime


class ExportHistoryResponse(BaseModel):
    id: UUID
    export_type: str
    format: str
    status: str
    file_url: Optional[str]
    created_at: datetime


# ─── Enforcement Schemas ─────────────────────────────────

class RaidScheduleRequest(BaseModel):
    vendor_id: Optional[UUID] = None
    location_name: str
    address: str
    state: str
    city: str
    scheduled_date: datetime
    assigned_officers: List[UUID]
    notes: Optional[str] = None
    priority: SeverityEnum = SeverityEnum.medium


class RaidResponse(BaseModel):
    id: UUID
    location_name: str
    address: str
    state: str
    city: str
    scheduled_date: datetime
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WarningNoticeRequest(BaseModel):
    company_id: UUID
    subject: str
    message: str
    severity: SeverityEnum
    deadline_date: Optional[date] = None


class SeizureLogRequest(BaseModel):
    vendor_id: Optional[UUID] = None
    product_name: str
    quantity: int
    location_name: str
    state: str
    city: str
    officer_notes: str
    evidence_urls: Optional[List[str]] = None


# ─── NAFDAC Notification Schemas ─────────────────────────

class BroadcastRequest(BaseModel):
    title: str
    message: str
    severity: Optional[SeverityEnum] = None


class CompanyNotificationRequest(BaseModel):
    title: str
    message: str


class NotificationSettingsUpdate(BaseModel):
    notification_type: str
    channel: str  # 'push', 'email', 'sms', 'in_app'
    enabled: bool


# ─── Settings & Config Schemas ───────────────────────────

class SystemSettingsResponse(BaseModel):
    risk_levels: dict
    categories: list
    notification_defaults: dict


class RiskLevelConfig(BaseModel):
    counterfeit_threshold: float = 0.7
    suspicious_threshold: float = 0.4
    auto_escalate_critical: bool = True
    alert_on_recurring: bool = True


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    old_data: Optional[dict]
    new_data: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    role: str
    permissions: List[str]


class PermissionUpdateRequest(BaseModel):
    permissions: List[str]


# ─── Login Schema ─────────────────────────────────────────

class LoginRequest(BaseModel):
    identifier: str  # email or phone
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: OfficerResponse
