import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    alert_type = Column(String(50), nullable=True)
    # CHECK constraint: alert_type IN ('counterfeit', 'suspicious', 'bulk', 'recurring')
    severity = Column(String(50), nullable=True)
    # CHECK constraint: severity IN ('critical', 'high', 'medium', 'low')
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)  # 'metadata' is reserved in SQLAlchemy
    is_read = Column(Boolean, default=False)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    # Indexes (defined in Alembic migration, not ORM):
    # idx_alerts_company on company_id
    # idx_alerts_type on alert_type
    # idx_alerts_severity on severity
    # idx_alerts_created on created_at


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), nullable=True)
    # CHECK: notification_type IN ('scan_result', 'report_update', 'alert', 'system', 'achievement')
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSONB, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    channel = Column(String(50), nullable=True)
    # CHECK: channel IN ('push', 'email', 'sms', 'in_app')
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'notification_type', 'channel', name='uq_notification_prefs'),
    )
