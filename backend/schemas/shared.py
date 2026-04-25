"""Shared verification and location schemas."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID


# ─── Verification Schemas ────────────────────────────────

class NAFDACVerifyResponse(BaseModel):
    """NAFDAC number verification response."""
    is_valid: bool
    product_name: Optional[str] = None
    company_name: Optional[str] = None
    category: Optional[str] = None
    nafdac_number: str
    status: Optional[str] = None
    message: str


class BatchVerifyResponse(BaseModel):
    """Batch number verification response."""
    is_valid: bool
    product_name: Optional[str] = None
    batch_number: str
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None
    message: str


class ImageVerifyRequest(BaseModel):
    """Image verification request."""
    image_urls: List[str]
    nafdac_number: Optional[str] = None


class ImageVerifyResponse(BaseModel):
    """Image verification response."""
    scan_id: UUID
    status: str  # 'processing', 'authentic', 'suspicious', 'fake'
    confidence_score: Optional[float] = None
    message: str


class ProductPublicResponse(BaseModel):
    """Public product details response."""
    id: UUID
    name: str
    manufacturer_name: Optional[str]
    nafdac_number: str
    category: Optional[str] = None
    status: str
    image_urls: Optional[list] = None

model_config = ConfigDict()


# ─── Location Schemas ────────────────────────────────────

class StateResponse(BaseModel):
    """Nigerian state response."""
    id: int
    name: str
    capital: Optional[str] = None
    region: Optional[str] = None

model_config = ConfigDict()


class CityResponse(BaseModel):
    """City response."""
    name: str
    state: str


class ReverseGeocodeRequest(BaseModel):
    """Reverse geocode request."""
    latitude: float
    longitude: float


class ReverseGeocodeResponse(BaseModel):
    """Reverse geocode response."""
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    formatted_location: str


class RAGVerifyRequest(BaseModel):
    """RAG-based product verification request."""
    nafdac_no: str
    scanned_subcategory: str
