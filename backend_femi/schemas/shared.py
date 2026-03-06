from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


# ─── Verification Schemas ────────────────────────────────

class NAFDACVerifyResponse(BaseModel):
    is_valid: bool
    product_name: Optional[str] = None
    company_name: Optional[str] = None
    category: Optional[str] = None
    nafdac_number: str
    status: Optional[str] = None
    message: str


class BatchVerifyResponse(BaseModel):
    is_valid: bool
    product_name: Optional[str] = None
    batch_number: str
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None
    message: str


class ImageVerifyRequest(BaseModel):
    image_urls: List[str]
    nafdac_number: Optional[str] = None


class ImageVerifyResponse(BaseModel):
    scan_id: UUID
    status: str  # 'processing', 'authentic', 'suspicious', 'fake'
    confidence_score: Optional[float] = None
    message: str


class ProductPublicResponse(BaseModel):
    id: UUID
    name: str
    manufacturer_name: Optional[str]
    nafdac_number: str
    category: Optional[str] = None
    status: str
    image_urls: Optional[list] = None

    class Config:
        from_attributes = True


# ─── Location Schemas ────────────────────────────────────

class StateResponse(BaseModel):
    id: int
    name: str
    capital: Optional[str]
    region: Optional[str]

    class Config:
        from_attributes = True


class CityResponse(BaseModel):
    name: str
    state: str


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float


class ReverseGeocodeResponse(BaseModel):
    state: Optional[str]
    city: Optional[str]
    address: Optional[str]
    formatted_location: str


class RAGVerifyRequest(BaseModel):
    nafdac_no: str
    scanned_subcategory: str
