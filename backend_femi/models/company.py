"""
Company model — owned by Mr Openx.
This stub allows imports to resolve. Replace with the real implementation.
"""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from backend_femi.database import Base


class Company(Base):
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
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
