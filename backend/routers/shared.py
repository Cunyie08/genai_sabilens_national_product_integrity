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
from backend.utils.geocoder import reverse_geocode as _reverse_geocode
from backend.utils.response import error_response, success_response
import logging

logger = logging.getLogger("shared.router")

router = APIRouter(tags=["Shared"])


# ── Hardcoded Nigerian states/cities fallback (used when DB is unavailable) ──

_NIGERIAN_STATES = [
    {"name": "Abia", "capital": "Umuahia", "region": "South East"},
    {"name": "Adamawa", "capital": "Yola", "region": "North East"},
    {"name": "Akwa Ibom", "capital": "Uyo", "region": "South South"},
    {"name": "Anambra", "capital": "Awka", "region": "South East"},
    {"name": "Bauchi", "capital": "Bauchi", "region": "North East"},
    {"name": "Bayelsa", "capital": "Yenagoa", "region": "South South"},
    {"name": "Benue", "capital": "Makurdi", "region": "North Central"},
    {"name": "Borno", "capital": "Maiduguri", "region": "North East"},
    {"name": "Cross River", "capital": "Calabar", "region": "South South"},
    {"name": "Delta", "capital": "Asaba", "region": "South South"},
    {"name": "Ebonyi", "capital": "Abakaliki", "region": "South East"},
    {"name": "Edo", "capital": "Benin City", "region": "South South"},
    {"name": "Ekiti", "capital": "Ado-Ekiti", "region": "South West"},
    {"name": "Enugu", "capital": "Enugu", "region": "South East"},
    {"name": "FCT", "capital": "Abuja", "region": "North Central"},
    {"name": "Gombe", "capital": "Gombe", "region": "North East"},
    {"name": "Imo", "capital": "Owerri", "region": "South East"},
    {"name": "Jigawa", "capital": "Dutse", "region": "North West"},
    {"name": "Kaduna", "capital": "Kaduna", "region": "North West"},
    {"name": "Kano", "capital": "Kano", "region": "North West"},
    {"name": "Katsina", "capital": "Katsina", "region": "North West"},
    {"name": "Kebbi", "capital": "Birnin Kebbi", "region": "North West"},
    {"name": "Kogi", "capital": "Lokoja", "region": "North Central"},
    {"name": "Kwara", "capital": "Ilorin", "region": "North Central"},
    {"name": "Lagos", "capital": "Ikeja", "region": "South West"},
    {"name": "Nasarawa", "capital": "Lafia", "region": "North Central"},
    {"name": "Niger", "capital": "Minna", "region": "North Central"},
    {"name": "Ogun", "capital": "Abeokuta", "region": "South West"},
    {"name": "Ondo", "capital": "Akure", "region": "South West"},
    {"name": "Osun", "capital": "Osogbo", "region": "South West"},
    {"name": "Oyo", "capital": "Ibadan", "region": "South West"},
    {"name": "Plateau", "capital": "Jos", "region": "North Central"},
    {"name": "Rivers", "capital": "Port Harcourt", "region": "South South"},
    {"name": "Sokoto", "capital": "Sokoto", "region": "North West"},
    {"name": "Taraba", "capital": "Jalingo", "region": "North East"},
    {"name": "Yobe", "capital": "Damaturu", "region": "North East"},
    {"name": "Zamfara", "capital": "Gusau", "region": "North West"},
]

_STATE_CITIES = {
    "Lagos": ["Ikeja", "Victoria Island", "Lekki", "Surulere", "Ajah", "Yaba", "Ikoyi", "Badagry", "Epe", "Ikorodu"],
    "FCT": ["Abuja", "Gwagwalada", "Kuje", "Bwari", "Kwali"],
    "Rivers": ["Port Harcourt", "Obio-Akpor", "Eleme", "Okrika", "Oyigbo", "Bonny"],
    "Kano": ["Kano", "Fagge", "Dala", "Gwale", "Tarauni", "Nassarawa"],
    "Oyo": ["Ibadan", "Ogbomosho", "Oyo", "Iseyin", "Saki", "Kisi"],
    "Kaduna": ["Kaduna", "Zaria", "Kafanchan", "Saminaka", "Birnin Gwari"],
    "Anambra": ["Awka", "Onitsha", "Nnewi", "Ekwulobia", "Agulu"],
}


@router.get("/api/verify/nafdac/{number}", response_model=None)
async def verify_nafdac_number(
    number: str = Path(..., description="NAFDAC registration number"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Try the relational DB first
    try:
        result = await db.execute(select(Product).where(Product.nafdac_number == number))
        product = result.scalar_one_or_none()

        if product:
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
    except Exception as db_exc:
        logger.warning("DB unavailable for NAFDAC verify, falling back to ChromaDB: %s", db_exc)

    # 2. Fallback: query ChromaDB RAG (always available locally)
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ai_engine"))
        from ai_engine.rag_system.retrieval.retriever import NAFDACRetriever
        retriever = NAFDACRetriever()
        results = retriever.retrieve(query=number, n_results=1)
        if results:
            r = results[0]
            return success_response(
                data=NAFDACVerifyResponse(
                    is_valid=True,
                    product_name=r.get("product_name", ""),
                    company_name=r.get("manufacturer", ""),
                    category=r.get("category", ""),
                    nafdac_number=number,
                    status="registered",
                    message="NAFDAC number found in ChromaDB registry",
                ).model_dump()
            )
    except Exception as chroma_exc:
        logger.warning("ChromaDB NAFDAC lookup failed: %s", chroma_exc)

    # 3. Not found in any source
    return success_response(
        data=NAFDACVerifyResponse(
            is_valid=False,
            nafdac_number=number,
            message="NAFDAC number not found in registry",
        ).model_dump()
    )


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
    # Try DB first, fall back to hardcoded list
    try:
        result = await db.execute(select(NigerianState).order_by(NigerianState.name))
        states = result.scalars().all()
        if states:
            data = [
                {"id": str(state.id) if state.id else None, "name": state.name, "capital": state.capital, "region": state.region}
                for state in states
            ]
            return success_response(data=data)
    except Exception as db_exc:
        logger.warning("DB unavailable for states, using hardcoded fallback: %s", db_exc)

    # Fallback: return hardcoded Nigerian states
    return success_response(data=_NIGERIAN_STATES)


@router.get("/api/location/cities/{state}", response_model=None)
async def get_cities_by_state(
    state: str = Path(..., description="Nigerian state name"),
    db: AsyncSession = Depends(get_db),
):
    # Try DB first
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

        if cities:
            return success_response(data=[{"name": city, "state": state} for city in cities])
    except Exception as db_exc:
        logger.warning("DB unavailable for cities, using hardcoded fallback: %s", db_exc)

    # Fallback: return known cities or just the state capital
    fallback_cities = _STATE_CITIES.get(state)
    if not fallback_cities:
        # Find capital from states list
        state_info = next((s for s in _NIGERIAN_STATES if s["name"] == state), None)
        capital = state_info["capital"] if state_info else state
        fallback_cities = [capital]

    return success_response(data=[{"name": city, "state": state} for city in fallback_cities])


@router.post("/api/location/reverse-geocode", response_model=None)
async def reverse_geocode_endpoint(req: ReverseGeocodeRequest):
    try:
        state, lga = _reverse_geocode(req.latitude, req.longitude)
        if state and lga:
            formatted = f"{lga}, {state}, Nigeria"
        elif state:
            formatted = f"{state}, Nigeria"
        else:
            formatted = f"{req.latitude:.4f}° N, {req.longitude:.4f}° E"

        return success_response(
            data=ReverseGeocodeResponse(
                state=state,
                lga=lga,
                city=lga,       # backwards-compat alias
                address=None,
                formatted_location=formatted,
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
