"""Product models — owned by Mr Openx."""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, Date, ForeignKey, Numeric, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class ProductCategory(Base):
    """Product categories table."""
    __tablename__ = "product_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Product(Base):
    """Products table."""
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    nafdac_number = Column(String(100), unique=True, nullable=True)
    batch_number = Column(String(100), nullable=True)
    manufacturer_name = Column(String(255), nullable=True)
    manufacturing_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    ingredients = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)
    image_urls = Column(JSONB, nullable=True)
    master_artwork_url = Column(Text, nullable=True)
    status = Column(String(50), default="active")
    # status IN ('active', 'pending', 'expired', 'discontinued')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ProductBarcode(Base):
    """Product barcodes table."""
    __tablename__ = "product_barcodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    barcode_type = Column(String(50), nullable=True)
    # barcode_type IN ('UPC', 'EAN', 'QR', 'CODE128', 'OTHER')
    barcode_value = Column(String(255), nullable=False)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class ProductEmbedding(Base):
    """Product embeddings table (AI fingerprints)."""
    __tablename__ = "product_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    embedding_type = Column(String(50), nullable=False)
    # embedding_type IN ('visual', 'ocr', 'regulatory', 'fusion', 'multi_modal')
    embedding_vector = Column(LargeBinary, nullable=True)
    model_version = Column(String(50), nullable=True)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
