"""
Consumer scan endpoints.

POST /api/consumer/scan  — submit image + metadata, get AI verdict immediately
POST /api/consumer/scan/detect-product — quick product detection for front panel
GET  /api/consumer/scan/{scan_id} — retrieve a previously stored scan result
GET  /api/consumer/scans — list the current user's scan history (requires JWT)
DELETE /api/consumer/scan/{scan_id} — delete a specific scan
DELETE /api/consumer/scans/clear — clear all scan history
"""

import uuid
import logging
import asyncio
import base64
import tempfile
import os
from io import BytesIO
from typing import Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from PIL import Image

from backend.database import get_db, AsyncSessionLocal
from backend.utils.response import success_response, error_response
from backend.services.ai_integration import run_scan_analysis
from backend.models.scan import Scan, ScanAnalysis
from backend.utils.image_upload import upload_scan_image
from backend.dependencies import get_optional_user, get_current_user

logger = logging.getLogger("consumer.router")

router = APIRouter(prefix="/api/consumer", tags=["Consumer"])

# Thread pool for blocking Cloudinary uploads
_upload_executor = ThreadPoolExecutor(max_workers=2)


# ── Request / response schemas ────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Payload sent by the frontend when starting a scan."""
    image_data: str                              # base64 data-URL or remote URL (front)
    back_image_data: Optional[str] = None        # back panel
    nafdac_no: Optional[str] = ""
    category: Optional[str] = "unknown"
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    location_text: Optional[str] = ""
    purchase_channel: Optional[str] = "unknown"
    product_name: Optional[str] = ""


class ScanCreateRequest(BaseModel):
    """Request schema for manually saving a scan to history"""
    product_name: Optional[str] = None
    product_image_url: Optional[str] = None
    status: str  # authentic, suspicious, fake
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    nafdac_number: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence_score: Optional[float] = None
    scan_data: Optional[dict] = None
    timestamp: Optional[float] = None  # Add timestamp field


class DetectProductRequest(BaseModel):
    """Payload for quick product detection."""
    image_data: str = Field(..., description="Base64 encoded image data")
    phase: Optional[str] = Field("front", description="Scan phase: front or back")


class DetectProductResponse(BaseModel):
    """Response for product detection."""
    has_product: bool
    confidence: float
    message: str


# ── Verdict normalisation ─────────────────────────────────────────────────────

def _normalise_result(ai_result: dict) -> dict:
    """
    Pass the AI engine verdict through unchanged to the frontend.
    Always returns a dict safe for JSON serialisation.
    """
    verdict = ai_result.get("final_verdict", "FAKE")
    confidence = ai_result.get("final_score", 0.0)

    return {
        "scan_id": ai_result.get("scan_id") or str(uuid.uuid4()),
        "verdict": verdict,
        "final_verdict": verdict,
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
    user_id=None,
) -> Optional[str]:
    """
    Persist the scan result to the database.
    Returns the saved scan_id, or None if the save failed.
    """
    try:
        scan_id = uuid.UUID(data["scan_id"])
        
        # Check if scan already exists (prevent duplicates)
        async with AsyncSessionLocal() as check_session:
            existing = await check_session.execute(
                select(Scan).where(Scan.id == scan_id)
            )
            if existing.scalar_one_or_none():
                logger.info(f"Scan {scan_id} already exists, skipping duplicate save")
                return str(scan_id)
        
        evidence = data.get("evidence_package", {})

        lat = req.latitude if req.latitude is not None and req.latitude != 0.0 else None
        lng = req.longitude if req.longitude is not None and req.longitude != 0.0 else None
        location_text = req.location_text or (
            f"{lat:.5f}° N, {lng:.5f}° E" if lat is not None and lng is not None else None
        )

        all_image_urls = [u for u in [
            image_url,
            data.get("back_image_url"),
        ] if u]

        scan = Scan(
            id=scan_id,
            user_id=user_id,
            product_name=evidence.get("product_name") or req.product_name or None,
            category=req.category or None,
            nafdac_number=evidence.get("nafdac_number") or req.nafdac_no or None,
            batch_number=evidence.get("batch_number") or None,
            manufacturer=evidence.get("manufacturer") or None,
            status=data["verdict"],
            confidence_score=data["confidence_score"],
            similarity_score=data["confidence_pct"],
            latitude=lat,
            longitude=lng,
            location_text=location_text,
            image_url=image_url or None,
            back_image_url=data.get("back_image_url") or None,
            scan_image_urls=all_image_urls if all_image_urls else [],
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


# ── Quick Product Detection Endpoint ─────────────────────────────────────────

@router.post("/scan/detect-product", response_model=DetectProductResponse)
async def detect_product(
    req: DetectProductRequest,
    current_user=Depends(get_optional_user),
):
    """
    Quick detection to check if a product is present in the image.
    Used during front panel capture to validate before proceeding.
    """
    if not req.image_data:
        raise HTTPException(status_code=400, detail="image_data is required")

    temp_path = None
    
    try:
        # Remove data URL prefix if present
        image_data = req.image_data
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        # Decode base64 to image
        try:
            image_bytes = base64.b64decode(image_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")

        # Save temporarily to disk for OCR processing
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            pil_image = Image.open(BytesIO(image_bytes))
            # Convert RGBA to RGB if needed
            if pil_image.mode == 'RGBA':
                pil_image = pil_image.convert('RGB')
            pil_image.save(tmp_file.name, 'JPEG', quality=85)
            temp_path = tmp_file.name
        
        # Use your existing OCR extractor
        try:
            from ocr_linguistic.extractor import extract_text_blocks, build_raw_text
            
            # Extract text blocks from the image
            blocks = extract_text_blocks(temp_path)
            raw_text = build_raw_text(blocks)
            text_length = len(raw_text.strip()) if raw_text else 0
            
            # Simple heuristic: product labels usually have text
            if text_length > 30:
                has_product = True
                confidence = min(0.95, text_length / 150)
            elif text_length > 10:
                has_product = True
                confidence = 0.65
            elif text_length > 0:
                has_product = True
                confidence = 0.45
            else:
                # No text detected - check if there's any OCR blocks at all
                has_product = len(blocks) > 0
                confidence = 0.25 if has_product else 0.15
            
            message = "Product detected" if has_product else "No product detected. Please ensure the product label is clearly visible and well-lit."
            
            logger.info(f"Product detection: has_product={has_product}, confidence={confidence}, text_length={text_length}, blocks={len(blocks)}")
            
            return DetectProductResponse(
                has_product=has_product,
                confidence=round(confidence, 2),
                message=message
            )
            
        except ImportError as e:
            # Fallback if OCR module not available
            logger.warning(f"OCR module import error: {e}")
            # Simple fallback: assume product exists if image has reasonable size
            image_size = len(image_bytes)
            has_product = image_size > 10000  # >10KB
            confidence = 0.5 if has_product else 0.3
            
            return DetectProductResponse(
                has_product=has_product,
                confidence=confidence,
                message="Product detection limited (OCR unavailable)"
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Product detection failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Product detection failed: {str(exc)}")
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")


# ── Main Scan Endpoint ────────────────────────────────────────────────────────

@router.post("/scan")
async def submit_scan(
    req: ScanRequest,
    current_user=Depends(get_optional_user),
):
    """Submit a product scan and get AI verdict."""
    if not req.image_data:
        return error_response("image_data is required", code="MISSING_IMAGE", status_code=400)

    try:
        ai_result = await run_scan_analysis(
            image_data=req.image_data,
            back_image_data=req.back_image_data,
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

        # Upload images to Cloudinary
        loop = asyncio.get_event_loop()

        image_url = await loop.run_in_executor(
            _upload_executor, upload_scan_image, req.image_data,
        )
        if image_url:
            data["image_url"] = image_url
            logger.info("Front image uploaded: %s", image_url)

        # Upload back image if present
        if req.back_image_data:
            back_url = await loop.run_in_executor(_upload_executor, upload_scan_image, req.back_image_data)
            if back_url:
                data["back_image_url"] = back_url
                logger.info("Back image uploaded: %s", back_url)

        # Save scan to DB in background
        # user_id = current_user.id if current_user else None
        # asyncio.create_task(_save_scan_to_db(data, req, image_url, user_id=user_id))

        return success_response(data=data, message="Scan analysis complete")

    except Exception as exc:
        logger.exception("Scan pipeline failed: %s", exc)
        return error_response(str(exc), code="SCAN_ERROR", status_code=500)


# ── Scan History Endpoints ────────────────────────────────────────────────────

@router.get("/scans")
async def get_user_scans(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get current user's scan history.
    Requires authentication (JWT token).
    """
    try:
        stmt = select(Scan).where(
            Scan.user_id == current_user.id
        ).order_by(
            Scan.created_at.desc()
        ).limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        scans = result.scalars().all()
        
        # Get total count for pagination
        count_stmt = select(func.count()).select_from(Scan).where(Scan.user_id == current_user.id)
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar()
        
        scans_data = []
        for scan in scans:
            # Convert Decimal to float for JSON serialization
            confidence = scan.confidence_score
            if confidence is not None:
                try:
                    confidence = float(confidence)
                except:
                    pass
            
            similarity = scan.similarity_score
            if similarity is not None:
                try:
                    similarity = float(similarity)
                except:
                    pass
            
            # Use image_url as the product image URL
            product_image = scan.image_url or getattr(scan, 'product_image_url', None)
            
            scans_data.append({
                "id": str(scan.id),
                "product_name": scan.product_name,
                "product_image_url": product_image,
                "status": scan.status,
                "category": scan.category,
                "manufacturer": scan.manufacturer,
                "nafdac_number": scan.nafdac_number,
                "batch_number": scan.batch_number,
                "expiry_date": scan.expiry_date.isoformat() if scan.expiry_date else None,
                "location_text": scan.location_text,
                "latitude": scan.latitude,
                "longitude": scan.longitude,
                "confidence_score": confidence,
                "similarity_score": similarity,
                "scan_data": scan.scan_data,
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
                "updated_at": scan.updated_at.isoformat() if hasattr(scan, 'updated_at') and scan.updated_at else None,
            })
        
        return success_response(
            data={
                "scans": scans_data,
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Scan history retrieved"
        )
        
    except Exception as e:
        logger.error(f"Error getting scan history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scans")
async def save_scan_to_history(
    scan_data: ScanCreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually save a scan to user's history.
    Requires authentication (JWT token).
    """
    try:
        # Generate a consistent ID based on user, product, and timestamp to prevent duplicates
        import hashlib
        
        # Use timestamp if provided, otherwise use current time
        timestamp = scan_data.timestamp or datetime.now().timestamp()
        unique_key = f"{current_user.id}_{scan_data.product_name}_{timestamp}"
        scan_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, unique_key)
        
        # Check if scan already exists
        existing = await db.execute(
            select(Scan).where(Scan.id == scan_uuid)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Scan {scan_uuid} already exists, skipping duplicate")
            return success_response(
                data={"id": str(scan_uuid), "already_exists": True},
                message="Scan already exists"
            )
        
        # Parse expiry date if provided
        expiry_date = None
        if scan_data.expiry_date:
            try:
                expiry_date = datetime.strptime(scan_data.expiry_date, "%Y-%m-%d").date()
            except ValueError:
                # Try alternative format
                try:
                    expiry_date = datetime.fromisoformat(scan_data.expiry_date).date()
                except:
                    logger.warning(f"Could not parse expiry date: {scan_data.expiry_date}")
        
        new_scan = Scan(
            id=scan_uuid,
            user_id=current_user.id,
            product_name=scan_data.product_name,
            image_url=scan_data.product_image_url,
            status=scan_data.status.upper(),
            category=scan_data.category,
            manufacturer=scan_data.manufacturer,
            nafdac_number=scan_data.nafdac_number,
            batch_number=scan_data.batch_number,
            expiry_date=expiry_date,
            location_text=scan_data.location_text,
            latitude=scan_data.latitude,
            longitude=scan_data.longitude,
            confidence_score=scan_data.confidence_score,
            scan_data=scan_data.scan_data or {}
        )
        
        db.add(new_scan)
        await db.commit()
        await db.refresh(new_scan)
        
        return success_response(
            data={
                "id": str(new_scan.id),
                "created_at": new_scan.created_at.isoformat() if new_scan.created_at else None
            },
            message="Scan saved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error saving scan: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/{scan_id}")
async def get_scan_by_id(
    scan_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific scan by ID.
    Requires authentication (JWT token).
    """
    try:
        # Validate UUID format
        try:
            scan_uuid = uuid.UUID(scan_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scan ID format")
        
        stmt = select(Scan).where(
            Scan.id == scan_uuid,
            Scan.user_id == current_user.id
        )
        result = await db.execute(stmt)
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Convert Decimal to float
        confidence = scan.confidence_score
        if confidence is not None:
            try:
                confidence = float(confidence)
            except:
                pass
        
        similarity = scan.similarity_score
        if similarity is not None:
            try:
                similarity = float(similarity)
            except:
                pass
        
        product_image = scan.image_url or getattr(scan, 'product_image_url', None)
        
        return success_response(data={
            "id": str(scan.id),
            "product_name": scan.product_name,
            "product_image_url": product_image,
            "status": scan.status,
            "category": scan.category,
            "manufacturer": scan.manufacturer,
            "nafdac_number": scan.nafdac_number,
            "batch_number": scan.batch_number,
            "expiry_date": scan.expiry_date.isoformat() if scan.expiry_date else None,
            "location_text": scan.location_text,
            "latitude": scan.latitude,
            "longitude": scan.longitude,
            "confidence_score": confidence,
            "similarity_score": similarity,
            "scan_data": scan.scan_data,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "updated_at": scan.updated_at.isoformat() if hasattr(scan, 'updated_at') and scan.updated_at else None
        }, message="Scan retrieved")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scan/{scan_id}")
async def delete_scan(
    scan_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a specific scan.
    Requires authentication (JWT token).
    """
    try:
        # Validate UUID format
        try:
            scan_uuid = uuid.UUID(scan_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scan ID format")
        
        stmt = delete(Scan).where(
            Scan.id == scan_uuid,
            Scan.user_id == current_user.id
        )
        result = await db.execute(stmt)
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return success_response(message="Scan deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scan: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scans/clear")
async def clear_all_scans(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear all scans for current user.
    Requires authentication (JWT token).
    """
    try:
        stmt = delete(Scan).where(Scan.user_id == current_user.id)
        result = await db.execute(stmt)
        await db.commit()
        
        return success_response(
            data={"deleted_count": result.rowcount},
            message=f"Cleared {result.rowcount} scans"
        )
        
    except Exception as e:
        logger.error(f"Error clearing scans: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/health")
async def scan_health():
    """Quick liveness check for the consumer scan service."""
    return success_response(data={"status": "ok"}, message="Consumer scan service is running")


@router.get("/scans/stats")
async def get_scan_stats(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get scan statistics for current user.
    Requires authentication (JWT token).
    """
    try:
        # Get total count
        total_stmt = select(func.count()).select_from(Scan).where(Scan.user_id == current_user.id)
        total_result = await db.execute(total_stmt)
        total = total_result.scalar() or 0
        
        # Get counts by status
        authentic_stmt = select(func.count()).select_from(Scan).where(
            Scan.user_id == current_user.id,
            Scan.status == "AUTHENTIC"
        )
        authentic_result = await db.execute(authentic_stmt)
        authentic = authentic_result.scalar() or 0
        
        suspicious_stmt = select(func.count()).select_from(Scan).where(
            Scan.user_id == current_user.id,
            Scan.status == "SUSPICIOUS"
        )
        suspicious_result = await db.execute(suspicious_stmt)
        suspicious = suspicious_result.scalar() or 0
        
        fake_stmt = select(func.count()).select_from(Scan).where(
            Scan.user_id == current_user.id,
            Scan.status == "FAKE"
        )
        fake_result = await db.execute(fake_stmt)
        fake = fake_result.scalar() or 0
        
        return success_response(data={
            "total": total,
            "authentic": authentic,
            "suspicious": suspicious,
            "fake": fake
        }, message="Scan statistics retrieved")
        
    except Exception as e:
        logger.error(f"Error getting scan stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))