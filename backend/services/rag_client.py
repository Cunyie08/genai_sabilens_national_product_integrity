"""Client helpers for the external RAG verification service."""

from typing import Any

import httpx

from backend.config import settings


async def verify_product_with_rag(nafdac_no: str, scanned_subcategory: str) -> dict[str, Any]:
    payload = {
        "nafdac_no": nafdac_no,
        "scanned_subcategory": scanned_subcategory,
    }
    async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{settings.RAG_SERVICE_URL}/verify/product", json=payload)
        response.raise_for_status()
        return response.json()


async def rag_healthcheck() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{settings.RAG_SERVICE_URL}/verify/health")
        response.raise_for_status()
        return response.json()
