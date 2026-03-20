"""
Consumer scan endpoints.

POST /api/consumer/scan  — submit image + metadata, get AI verdict immediately
GET  /api/consumer/scan/{scan_id} — retrieve a previously stored scan result
GET  /api/consumer/scans — list the current user's scan history (requires JWT)
"""

import uuid
import logging
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, AsyncSessionLocal
from backend.utils.response import success_response, error_response
from backend.services.ai_integration import run_scan_analysis
from backend.models.scan import Scan, ScanAnalysis
from backend.utils.image_upload import upload_scan_image

logger = logging.getLogger("consumer.router")

router = APIRouter(prefix="/api/consumer", tags=["Consumer"])

# Thread pool for blocking Cloudinary uploads
_upload_executor = ThreadPoolExecutor(max_workers=2)


# ── Request / response schemas ────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Payload sent by the frontend when starting a scan."""
    image_data: str                              # base64 data-URL or remote URL (front / phase-0)
    back_image_data: Optional[str] = None        # back panel (phase-1)
    side_image_data: Optional[str] = None        # side panel (phase-2)
    detail_image_data: Optional[str] = None      # detail / seal (phase-3)
    nafdac_no: Optional[str] = ""
    category: Optional[str] = "unknown"
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    location_text: Optional[str] = ""
    purchase_channel: Optional[str] = "unknown"
    product_name: Optional[str] = ""


# ── Verdict normalisation ─────────────────────────────────────────────────────

def _normalise_result(ai_result: dict) -> dict:
    """
    Pass the AI engine verdict through unchanged to the frontend.
    Always returns a dict safe for JSON serialisation.
    """
    verdict = ai_result.get("final_verdict", "FAKE")   # exact AI verdict: AUTHENTIC | SUSPICIOUS | FAKE | RESCAN_REQUIRED
    confidence = ai_result.get("final_score", 0.0)

    return {
        "scan_id": ai_result.get("scan_id") or str(uuid.uuid4()),
        "verdict": verdict,                            # exact AI verdict (uppercase)
        "final_verdict": verdict,                      # same field — no transformation
        "confidence_score": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "severity": ai_result.get("final_severity", "CRITICAL"),
        "action": ai_result.get("action", "DO NOT BUY"),
        "simple_instruction": ai_result.get("simple_instruction", ""),
        "status": ai_result.get("status", "FAILSAFE"),
        "summary": ai_result.get("summary", ""),
        "detail": ai_result.get("detail", ""),
        "report_priority": ai_result.get("report_priority", "NONE"),
        "override_applied": ai_result.get("override_applied", False),
        "override_summary": ai_result.get("override_summary", ""),
        "warnings": ai_result.get("warnings", []),
        "breakdown": ai_result.get("breakdown", {}),
        "evidence_package": ai_result.get("evidence_package", {}),
        "rescan_required": ai_result.get("rescan_required", False),
        "signals_used": ai_result.get("signals_used", []),
        "ai_signals": {
            "ocr_mocked": ai_result.get("ocr_mocked", True),
            "vision_mocked": ai_result.get("vision_mocked", True),
        },
    }


async def _save_scan_to_db(
    data: dict,
    req: ScanRequest,
    image_url: Optional[str],
) -> Optional[str]:
    """
    Persist the scan result to the database.
    Returns the saved scan_id, or None if the save failed.
    This is called after the AI result is already returned to the client,
    so any failure here does not affect the user-facing response.
    """
    try:
        evidence = data.get("evidence_package", {})

        # Use None (not 0.0) to distinguish "no GPS" from coordinates at the equator
        lat = req.latitude if req.latitude is not None and req.latitude != 0.0 else None
        lng = req.longitude if req.longitude is not None and req.longitude != 0.0 else None
        location_text = req.location_text or (
            f"{lat:.5f}° N, {lng:.5f}° E" if lat is not None and lng is not None else None
        )

        all_image_urls = [u for u in [
            image_url,
            data.get("back_image_url"),
            data.get("side_image_url"),
            data.get("detail_image_url"),
        ] if u]

        scan = Scan(
            id=uuid.UUID(data["scan_id"]),
            product_name=evidence.get("product_name") or req.product_name or None,
            category=req.category or None,
            nafdac_number=evidence.get("nafdac_number") or req.nafdac_no or None,
            batch_number=evidence.get("batch_number") or None,
            manufacturer=evidence.get("manufacturer") or None,
            status=data["verdict"],                         # AUTHENTIC | SUSPICIOUS | FAKE | RESCAN_REQUIRED
            confidence_score=data["confidence_score"],
            similarity_score=data["confidence_pct"],
            # GPS — stored as proper Float columns in the DB
            latitude=lat,
            longitude=lng,
            location_text=location_text,
            # Images
            image_url=image_url or None,
            back_image_url=data.get("back_image_url") or None,
            scan_image_urls=all_image_urls if all_image_urls else [],
            # side and detail URLs stored in scan_data (no dedicated columns)

            # Full AI result as JSON
            scan_data={
                "verdict": data["verdict"],
                "final_verdict": data["final_verdict"],
                "confidence_pct": data["confidence_pct"],
                "severity": data["severity"],
                "action": data["action"],
                "summary": data["summary"],
                "detail": data["detail"],
                "warnings": data["warnings"],
                "signals_used": data["signals_used"],
                "ai_signals": data["ai_signals"],
                "purchase_channel": req.purchase_channel,
                "latitude": lat,
                "longitude": lng,
                "location_text": location_text,
            },
        )

        async with AsyncSessionLocal() as session:
            session.add(scan)
            await session.commit()
            logger.info("Scan saved to DB: id=%s verdict=%s", scan.id, scan.status)
            return str(scan.id)

    except Exception as exc:
        logger.warning("DB save failed (non-fatal): %s", exc)
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan")
async def submit_scan(req: ScanRequest):
    """
    Run the full AI scan pipeline on the submitted product image.

    Accepts a base64 data-URL (from camera capture) or a remote image URL
    (e.g. from Cloudinary). Returns the complete AI verdict synchronously,
    then asynchronously uploads the image and saves the scan record to the DB.
    """
    if not req.image_data:
        return error_response("image_data is required", code="MISSING_IMAGE", status_code=400)

    try:
        ai_result = await run_scan_analysis(
            image_data=req.image_data,
            back_image_data=req.back_image_data,
            side_image_data=req.side_image_data,
            detail_image_data=req.detail_image_data,
            nafdac_no=req.nafdac_no or "",
            category=req.category or "unknown",
            latitude=req.latitude or 0.0,
            longitude=req.longitude or 0.0,
            purchase_channel=req.purchase_channel or "unknown",
        )
        data = _normalise_result(ai_result)
        logger.info(
            "Scan complete | verdict=%s | score=%.3f | scan_id=%s | images=%d",
            data["final_verdict"], data["confidence_score"], data["scan_id"],
            ai_result.get("image_count", 1),
        )

        # Upload all provided images to Cloudinary (non-blocking)
        loop = asyncio.get_event_loop()

        image_url = await loop.run_in_executor(
            _upload_executor, upload_scan_image, req.image_data,
        )
        if image_url:
            data["image_url"] = image_url
            logger.info("Front image uploaded: %s", image_url)

        for attr, key, label in [
            ("back_image_data",   "back_image_url",   "Back"),
            ("side_image_data",   "side_image_url",   "Side"),
            ("detail_image_data", "detail_image_url", "Detail"),
        ]:
            raw = getattr(req, attr, None)
            if raw:
                url = await loop.run_in_executor(_upload_executor, upload_scan_image, raw)
                if url:
                    data[key] = url
                    logger.info("%s image uploaded: %s", label, url)

        # Save scan to DB in background — failure does not block the response
        asyncio.create_task(_save_scan_to_db(data, req, image_url))

        return success_response(data=data, message="Scan analysis complete")

    except Exception as exc:
        logger.exception("Scan pipeline failed: %s", exc)
        return error_response(str(exc), code="SCAN_ERROR", status_code=500)


@router.get("/scan/health")
async def scan_health():
    """Quick liveness check for the consumer scan service."""
    return success_response(data={"status": "ok"}, message="Consumer scan service is running")
