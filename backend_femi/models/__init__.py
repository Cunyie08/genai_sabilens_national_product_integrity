# Register all models here so Alembic detects them for migrations.

from backend_femi.models.user import User
from backend_femi.models.company import Company
from backend_femi.models.product import Product, ProductCategory
from backend_femi.models.scan import Scan
from backend_femi.models.report import Report, ReportEvidence
from backend_femi.models.alert import Alert, Notification, NotificationPreference
from backend_femi.models.analytics import (
    AnalyticsDaily,
    AnalyticsCategory,
    AnalyticsRegion,
    Hotspot,
    VendorLocation,
    NigerianState,
    Language,
    AuditLog,
    SystemLog,
)

__all__ = [
    "User",
    "Company",
    "Product",
    "ProductCategory",
    "Scan",
    "Report",
    "ReportEvidence",
    "Alert",
    "Notification",
    "NotificationPreference",
    "AnalyticsDaily",
    "AnalyticsCategory",
    "AnalyticsRegion",
    "Hotspot",
    "VendorLocation",
    "NigerianState",
    "Language",
    "AuditLog",
    "SystemLog",
]
