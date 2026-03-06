"""
Scan model — owned by tunjipaul.
This stub allows imports to resolve. Replace with the real implementation.
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from backend_femi.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=True)
    # status IN ('processing', 'authentic', 'suspicious', 'fake')
    confidence_score = Column(Numeric(5, 4), nullable=True)
    scan_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
