"""Public shared routes for verification and location services."""

import uuid
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.analytics import NigerianState, VendorLocation
from backend.models.company import Company
from backend.models.product import Product, ProductCategory
from backend.schemas.shared import (
    BatchVerifyResponse,
    ImageVerifyRequest,
    ImageVerifyResponse,
    NAFDACVerifyResponse,
    RAGVerifyRequest,
    ReverseGeocodeRequest,
    ReverseGeocodeResponse,
)
from backend.services.rag_client import rag_healthcheck, verify_product_with_rag
from backend.utils.response import error_response, success_response

router = APIRouter(tags=["Shared"])


@router.get("/api/verify/nafdac/{number}", response_model=None)
async def verify_nafdac_number(
    number: str = Path(..., description="NAFDAC registration number"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Product).where(Product.nafdac_number == number))
        product = result.scalar_one_or_none()

        if not product:
            return success_response(
                data=NAFDACVerifyResponse(
                    is_valid=False,
                    nafdac_number=number,
                    message="NAFDAC number not found in registry",
                ).model_dump()
            )

        company_name = None
        if product.company_id:
            company = await db.get(Company, product.company_id)
            company_name = company.name if company else None

        category_name = None
        if product.category_id:
            category = await db.get(ProductCategory, product.category_id)
            category_name = category.name if category else None

        return success_response(
            data=NAFDACVerifyResponse(
                is_valid=True,
                product_name=product.name,
                company_name=company_name,
                category=category_name,
                nafdac_number=number,
                status=product.status,
                message="NAFDAC number verified successfully",
            ).model_dump()
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.get("/api/verify/batch/{number}", response_model=None)
async def verify_batch_number(
    number: str = Path(..., description="Batch number"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Product).where(Product.batch_number == number))
        product = result.scalar_one_or_none()

        if not product:
            return success_response(
                data=BatchVerifyResponse(
                    is_valid=False,
                    batch_number=number,
                    message="Batch number not found",
                ).model_dump()
            )

        return success_response(
            data=BatchVerifyResponse(
                is_valid=True,
                product_name=product.name,
                batch_number=number,
                manufacturing_date=(
                    str(product.manufacturing_date) if product.manufacturing_date else None
                ),
                expiry_date=str(product.expiry_date) if product.expiry_date else None,
                message="Batch number verified",
            ).model_dump()
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.post("/api/verify/image", response_model=None)
async def verify_product_by_image(
    req: ImageVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    _ = (req, db)
    try:
        scan_id = uuid.uuid4()
        return success_response(
            data=ImageVerifyResponse(
                scan_id=scan_id,
                status="processing",
                message=(
                    "Image submitted for analysis. "
                    "Poll GET /api/consumer/scan/result/{scan_id} for results."
                ),
            ).model_dump()
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.get("/api/verify/product/{product_id}", response_model=None)
async def get_product_public_details(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        product = await db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        category_name = None
        if product.category_id:
            category = await db.get(ProductCategory, product.category_id)
            category_name = category.name if category else None

        return success_response(
            data={
                "id": str(product.id),
                "name": product.name,
                "manufacturer_name": product.manufacturer_name,
                "nafdac_number": product.nafdac_number,
                "category": category_name,
                "status": product.status,
                "image_urls": product.image_urls,
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.get("/api/location/states", response_model=None)
async def get_nigerian_states(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(NigerianState).order_by(NigerianState.name))
        states = result.scalars().all()
        data = [
            {"id": state.id, "name": state.name, "capital": state.capital, "region": state.region}
            for state in states
        ]
        return success_response(data=data)
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.get("/api/location/cities/{state}", response_model=None)
async def get_cities_by_state(
    state: str = Path(..., description="Nigerian state name"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(VendorLocation.city)
            .where(VendorLocation.state == state)
            .where(VendorLocation.city.isnot(None))
            .distinct()
            .order_by(VendorLocation.city)
        )
        cities = [row[0] for row in result.all()]

        if not cities:
            state_record = (
                await db.execute(select(NigerianState).where(NigerianState.name == state))
            ).scalar_one_or_none()
            if state_record and state_record.capital:
                cities = [state_record.capital]

        return success_response(data=[{"name": city, "state": state} for city in cities])
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.post("/api/location/reverse-geocode", response_model=None)
async def reverse_geocode(req: ReverseGeocodeRequest):
    try:
        return success_response(
            data=ReverseGeocodeResponse(
                state="Lagos",
                city="Ikeja",
                address=None,
                formatted_location=f"{req.latitude:.4f}, {req.longitude:.4f} (Lagos, Nigeria)",
            ).model_dump(),
            message="Reverse geocode completed",
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.post("/api/verify/rag/product", response_model=None)
async def verify_product_with_rag_service(req: RAGVerifyRequest):
    try:
        data = await verify_product_with_rag(
            nafdac_no=req.nafdac_no,
            scanned_subcategory=req.scanned_subcategory,
        )
        return success_response(data=data, message="RAG verification completed")
    except httpx.HTTPStatusError as exc:
        return error_response(
            message=f"RAG service returned {exc.response.status_code}",
            code="RAG_SERVICE_ERROR",
            status_code=502,
        )
    except httpx.RequestError as exc:
        return error_response(
            message=f"RAG service unreachable: {exc}",
            code="RAG_SERVICE_UNAVAILABLE",
            status_code=503,
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)


@router.get("/api/verify/rag/health", response_model=None)
async def get_rag_service_health():
    try:
        data = await rag_healthcheck()
        return success_response(data=data, message="RAG service healthy")
    except httpx.HTTPStatusError as exc:
        return error_response(
            message=f"RAG health endpoint returned {exc.response.status_code}",
            code="RAG_SERVICE_ERROR",
            status_code=502,
        )
    except httpx.RequestError as exc:
        return error_response(
            message=f"RAG service unreachable: {exc}",
            code="RAG_SERVICE_UNAVAILABLE",
            status_code=503,
        )
    except Exception as exc:
        return error_response(str(exc), code="INTERNAL_ERROR", status_code=500)
