"""User and authentication models — owned by tunjipaul."""
import uuid
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class UserRole(str, Enum):
    CONSUMER = "consumer"
    COMPANY_ADMIN = "company_admin"
    NAFDAC_OFFICER = "nafdac_officer"
    NAFDAC_ADMIN = "nafdac_admin"
    SUPER_ADMIN = "super_admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class User(Base):
    """Users table."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(String(50), nullable=False, default="consumer")
    # role IN ('consumer', 'company_admin', 'nafdac_officer', 'nafdac_admin', 'super_admin')
    status = Column(String(50), nullable=False, default="active")
    # status IN ('active', 'suspended', 'pending', 'deleted')
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    profile_image_url = Column(Text, nullable=True)
    preferred_language = Column(String(10), default="en")
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    # NEW: Location fields
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    last_login = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Session(Base):
    """Sessions table."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(Text, nullable=False)
    device_info = Column(JSONB, nullable=True)
    ip_address = Column(String(50), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class OTPVerification(Base):
    """OTP verifications table."""
    __tablename__ = "otp_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(String(50), nullable=True)
    # purpose IN ('registration', 'login', 'password_reset', 'phone_verification')
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())