"""NAFDAC request and response schemas"""
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime


class OfficerCreateRequest(BaseModel):
    """Create NAFDAC officer"""
    email: EmailStr
    phone: str
    first_name: str
    last_name: str
    role: str  # nafdac_officer, nafdac_admin
    state: Optional[str] = None  # Assigned state


class OfficerResponse(BaseModel):
    """Officer response"""
    id: str
    email: str
    phone: str
    first_name: str
    last_name: str
    role: str
    status: str
    state: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OfficersListResponse(BaseModel):
    """Officers list response"""
    officers: List[OfficerResponse]
    total: int


class CompanyVerificationRequest(BaseModel):
    """Verify company request"""
    company_id: str
    verified: bool
    notes: Optional[str] = None


class CompanyDetailResponse(BaseModel):
    """Company detail response"""
    id: str
    name: str
    registration_number: str
    email: str
    phone: str
    status: str
    subscription_tier: str
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    created_at: datetime


class CaseCreateRequest(BaseModel):
    """Create case request"""
    report_id: str
    priority: str  # critical, high, medium, low
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CaseResponse(BaseModel):
    """Case response"""
    id: str
    case_number: str
    report_id: Optional[str] = None
    assigned_to: Optional[str] = None
    case_status: str
    priority: str
    description: Optional[str] = None
    officer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    """Cases list response"""
    cases: List[CaseResponse]
    total: int
    page: int
    limit: int


class AlertAcknowledgeRequest(BaseModel):
    """Acknowledge alert request"""
    alert_id: str
    notes: Optional[str] = None


class AlertResponse(BaseModel):
    """Alert response (NAFDAC view)"""
    id: str
    report_id: Optional[str] = None
    alert_type: str
    severity: str
    title: str
    message: str
    is_acknowledged: bool
    acknowledged_by: Optional[str] = None
    created_at: datetime


class AlertListResponse(BaseModel):
    """Alerts list response"""
    alerts: List[AlertResponse]
    total: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class EnforcementActionCreateRequest(BaseModel):
    """Create enforcement action"""
    case_id: str
    action_type: str  # raid, seizure, notice, suspension, prosecution
    description: Optional[str] = None
    quantity_seized: Optional[int] = None
    seized_items_description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EnforcementActionResponse(BaseModel):
    """Enforcement action response"""
    id: str
    case_id: str
    action_type: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    executed_by: Optional[str] = None
    execution_date: Optional[datetime] = None
    quantity_seized: Optional[int] = None
    action_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class VendorResponse(BaseModel):
    """Vendor response"""
    id: str
    vendor_name: str
    city: str
    state: str
    report_count: int
    risk_level: str
    is_blacklisted: bool
    blacklisted_at: Optional[datetime] = None
    last_reported_at: Optional[datetime] = None


class VendorListResponse(BaseModel):
    """Vendors list response"""
    vendors: List[VendorResponse]
    total: int
    high_risk_count: int


class AnalyticsResponse(BaseModel):
    """Analytics data response"""
    total_scans: int
    authentic_scans: int
    suspicious_scans: int
    counterfeit_scans: int
    total_reports: int
    reports_verified: int
    cases_active: int
    cases_closed: int


class CategoryAnalyticsResponse(BaseModel):
    """Category analytics"""
    category_name: str
    scan_count: int
    counterfeit_count: int
    suspicious_count: int
    authentic_count: int
    risk_percentage: float


class RegionalAnalyticsResponse(BaseModel):
    """Regional analytics"""
    state: str
    city: Optional[str] = None
    scan_count: int
    counterfeit_count: int
    risk_score: float
    risk_level: str


class TrendDataPoint(BaseModel):
    """Trend data point"""
    date: str
    scans: int
    counterfeits: int
    reports: int


class TrendsResponse(BaseModel):
    """Trends response"""
    trends: List[TrendDataPoint]
    period: str  # daily, weekly, monthly


class HotspotResponse(BaseModel):
    """Hotspot response"""
    id: str
    region_name: str
    city: str
    state: str
    latitude: float
    longitude: float
    report_count: int
    severity_score: float
    risk_level: str


class HotspotsResponse(BaseModel):
    """Hotspots response"""
    hotspots: List[HotspotResponse]
    total: int


class DashboardStatsResponse(BaseModel):
    """National dashboard stats"""
    total_scans_today: int
    total_scans_month: int
    authentic_today: int
    counterfeit_today: int
    suspicious_today: int
    active_cases: int
    critical_alerts: int
    verified_companies: int
    high_risk_states: int


class LiveAlertResponse(BaseModel):
    """Live alert for dashboard"""
    id: str
    timestamp: datetime
    alert_type: str
    severity: str
    location: str
    description: str
    company_name: Optional[str] = None


class LiveAlertsResponse(BaseModel):
    """Live alerts response"""
    alerts: List[LiveAlertResponse]
    total: int


class ExportRequest(BaseModel):
    """Export data request"""
    export_type: str  # reports, cases, vendors, analytics
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "csv"  # csv, pdf, xlsx


class ExportResponse(BaseModel):
    """Export response"""
    export_id: str
    status: str  # pending, processing, completed, failed
    created_at: datetime
    download_url: Optional[str] = None
