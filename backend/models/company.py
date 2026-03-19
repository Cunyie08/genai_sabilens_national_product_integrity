"""Company models — owned by Mr Openx."""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, Numeric, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Company(Base):
    """Companies table."""
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    registration_number = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), default="Nigeria")
    logo_url = Column(String(500), nullable=True)
    website = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    # status IN ('pending', 'active', 'suspended', 'rejected')
    subscription_tier = Column(String(50), default="basic")
    # subscription_tier IN ('free', 'basic', 'premium', 'enterprise')
    subscription_expires_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CompanySettings(Base):
    """Company settings table."""
    __tablename__ = "company_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True)
    notification_email = Column(Boolean, default=True)
    notification_alerts = Column(Boolean, default=True)
    notification_reports = Column(Boolean, default=True)
    auto_export_enabled = Column(Boolean, default=False)
    api_access_enabled = Column(Boolean, default=False)
    webhook_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CompanyAPIKey(Base):
    """Company API keys table."""
    __tablename__ = "company_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False)
    api_secret = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    permissions = Column(JSONB, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class SubscriptionPlan(Base):
    """Subscription plans table."""
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    tier = Column(String(50), unique=True, nullable=False)
    # tier IN ('free', 'basic', 'premium', 'enterprise')
    description = Column(Text, nullable=True)
    price_monthly = Column(Numeric(10, 2), nullable=True)
    price_annual = Column(Numeric(10, 2), nullable=True)
    features = Column(JSONB, nullable=True)
    max_scans_monthly = Column(Integer, nullable=True)
    max_products = Column(Integer, nullable=True)
    max_team_members = Column(Integer, nullable=True)
    api_access = Column(Boolean, default=False)
    webhook_support = Column(Boolean, default=False)
    priority_support = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WebhookLog(Base):
    """Webhook logs table."""
    __tablename__ = "webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    webhook_url = Column(Text, nullable=False)
    event_type = Column(String(100), nullable=True)
    payload = Column(JSONB, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
