# Register all models here so Alembic detects them for migrations.

from backend.models.user import User
from backend.models.company import Company
from backend.models.product import Product, ProductCategory
from backend.models.scan import Scan
from backend.models.report import Report, ReportEvidence
from backend.models.alert import Alert, Notification, NotificationPreference
from backend.models.analytics import (
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
