"""
Product model — owned by Mr Openx.
This stub allows imports to resolve. Replace with the real implementation.
"""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    nafdac_number = Column(String(100), unique=True, nullable=True)
    batch_number = Column(String(100), nullable=True)
    manufacturer_name = Column(String(255), nullable=True)
    manufacturing_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(50), default="active")
    image_urls = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
