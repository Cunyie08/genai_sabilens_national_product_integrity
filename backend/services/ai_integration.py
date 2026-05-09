"""
AI Engine integration bridge.

Connects the FastAPI backend to the ScanOrchestrator pipeline.
Handles:
  - Image ingestion (base64 data URLs or remote URLs)
  - Thread-pool execution of the synchronous AI pipeline
  - Returning a normalised result dict to the caller
"""

import asyncio
import base64
import logging
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from backend.config import settings

# Register HEIC/HEIF support with Pillow so iPhone photos in HEIC format
# can be opened by Image.open() throughout the process.
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    logging.getLogger("ai_integration").info("pillow_heif registered: HEIC images supported")
except ImportError:
    logging.getLogger("ai_integration").warning(
        "pillow_heif not installed; HEIC images will fail to open"
    )

logger = logging.getLogger("ai_integration")

# ── Python-path setup ────────────────────────────────────────────────────────
# Make the repo root and ai_engine importable regardless of how uvicorn is
# invoked (e.g. `uvicorn backend.main:app` from the repo root).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)                                   # repo root
_AI_ENGINE_DIR = os.path.join(_REPO_ROOT, "ai_engine")

for _p in (_REPO_ROOT, _AI_ENGINE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── DB category lookup (sync — used inside the thread pool) ──────────────────

def _make_category_resolver(db_url: str):
    """
    Return a sync callable(nafdac_no) -> Optional[str] that queries the products
    table joined to product_categories and returns the category name, or None if
    the NAFDAC number is not found.

    Uses a short-lived SQLAlchemy sync engine so the orchestrator thread can call
    it without needing an async event loop.  The asyncpg dialect prefix is swapped
    to psycopg2 so SQLAlchemy can use a sync driver.
    """
    import sqlalchemy as _sa

    # Convert "postgresql+asyncpg://..." to "postgresql+psycopg2://..."
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    # Also handle plain "postgresql://..." (already sync-compatible)

    _engine = None

    def _resolver(nafdac_no: str) -> Optional[str]:
        nonlocal _engine
        if not nafdac_no:
            return None
        try:
            if _engine is None:
                _engine = _sa.create_engine(
                    sync_url,
                    pool_size=1,
                    max_overflow=0,
                    pool_pre_ping=True,
                )
            with _engine.connect() as conn:
                row = conn.execute(
                    _sa.text(
                        "SELECT pc.name "
                        "FROM products p "
                        "JOIN product_categories pc ON pc.id = p.category_id "
                        "WHERE p.nafdac_number = :nafdac_no "
                        "LIMIT 1"
                    ),
                    {"nafdac_no": nafdac_no},
                ).fetchone()
            return row[0] if row else None
        except Exception:
            logger.warning(
                "DB category lookup failed for nafdac_no='%s'.", nafdac_no, exc_info=True
            )
            return None

    return _resolver


# ── Singleton orchestrator ────────────────────────────────────────────────────
_orchestrator = None
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-worker")
_category_resolver = _make_category_resolver(settings.DATABASE_URL)


def _get_orchestrator():
    """Return the singleton ScanOrchestrator, initialising it on first call."""
    global _orchestrator
    if _orchestrator is None:
        from ai_engine.orchestrator.scan_orchestrator import ScanOrchestrator  # noqa
        _orchestrator = ScanOrchestrator()
        logger.info("ScanOrchestrator initialised successfully.")
    return _orchestrator


# ── Image helpers ─────────────────────────────────────────────────────────────

async def _save_base64_image(data_url: str) -> str:
    """Write a base64 data-URL image to a temp file and return the path.

    HEIC/HEIF images (iPhone 14 Pro gallery exports) are converted to JPEG
    so downstream Pillow and Tesseract callers never see a HEIC extension.
    """
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    header_lower = header.lower()

    is_heic = "heic" in header_lower or "heif" in header_lower

    if is_heic:
        heic_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".heic")
        heic_tmp.write(img_bytes)
        heic_tmp.close()
        try:
            from PIL import Image as PILImage
            img = PILImage.open(heic_tmp.name).convert("RGB")
            jpg_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            img.save(jpg_tmp.name, "JPEG", quality=90)
            jpg_tmp.close()
            logger.info("HEIC → JPEG conversion succeeded: %s", jpg_tmp.name)
            return jpg_tmp.name
        except Exception as exc:
            logger.warning("HEIC conversion failed (%s); falling back to raw bytes", exc)
        finally:
            try:
                os.unlink(heic_tmp.name)
            except Exception:
                pass

    suffix = ".png" if "png" in header_lower else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(img_bytes)
    tmp.close()
    return tmp.name


def _resize_if_needed(path: str, max_px: int = 1920) -> str:
    """Resize image so its longest side ≤ max_px. Returns the (possibly new) path.

    Operates synchronously — call via run_in_executor from async code.
    If anything fails the original path is returned untouched.
    """
    try:
        from PIL import Image as PILImage
        img = PILImage.open(path)
        w, h = img.size
        if max(w, h) <= max_px:
            return path
        scale = max_px / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.convert("RGB").resize((new_w, new_h), PILImage.LANCZOS)
        new_path = path + "_r.jpg"
        img.save(new_path, "JPEG", quality=85)
        logger.info("Resized %dx%d → %dx%d: %s", w, h, new_w, new_h, new_path)
        try:
            os.unlink(path)
        except Exception:
            pass
        return new_path
    except Exception as exc:
        logger.warning("Image resize failed (%s); using original", exc)
        return path


async def _download_image(url: str) -> str:
    """Download a remote image to a temp file and return the path."""
    suffix = ".png" if ".png" in url.lower() else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    with open(tmp_path, "wb") as f:
        f.write(response.content)

    return tmp_path


async def _prepare_image(image_data: str) -> str:
    """
    Accept either:
      - a base64 data-URL  → write to temp file
      - a remote URL       → download to temp file
    Returns the temp file path.
    """
    if image_data.startswith("data:"):
        return await _save_base64_image(image_data)
    return await _download_image(image_data)


# ── Synchronous orchestrator runner (runs in thread pool) ────────────────────

def _run_orchestrator_sync(
    image_paths: list,
    nafdac_no: str,
    category: str,
    gps: dict,
    purchase_channel: str,
) -> dict:
    """
    Blocking call to ScanOrchestrator.scan().
    Must be executed via run_in_executor so the event loop is not blocked.
    image_paths: list of temp file paths; first is the primary (front) image.
    """
    orchestrator = _get_orchestrator()
    result = orchestrator.scan(
        image_path=image_paths[0],
        image_paths=image_paths,
        nafdac_no=nafdac_no,
        scanned_category=category,
        gps_coordinates=gps,
        purchase_channel=purchase_channel,
        category_resolver=_category_resolver,
    )

    return {
        "final_verdict": result.final_verdict,
        "final_score": float(result.final_score),
        "final_severity": result.final_severity,
        "action": result.action,
        "simple_instruction": result.simple_instruction,
        "status": result.status,
        "scan_id": result.scan_id,
        "summary": result.summary,
        "detail": result.detail,
        "report_priority": result.report_priority,
        "override_applied": result.override_applied,
        "override_summary": result.override_summary,
        "warnings": result.warnings,
        "breakdown": result.breakdown,
        "evidence_package": result.evidence_package,
        "rescan_required": result.rescan_required,
        "signals_used": result.signals_used,
        "ocr_mocked": result.ocr_signal.mocked,
        "vision_mocked": result.vision_signal.mocked,
    }


# ── Public async entry-point ─────────────────────────────────────────────────

async def run_scan_analysis(
    image_data: str,
    back_image_data: Optional[str] = None,
    nafdac_no: str = "",
    category: str = "unknown",
    latitude: float = 0.0,
    longitude: float = 0.0,
    purchase_channel: str = "unknown",
) -> dict:
    """
    Full scan pipeline:
      1. Save front and (optionally) back images to temp files.
      2. Run ScanOrchestrator in a thread pool (non-blocking) with both image paths.
      3. Clean up temp files.
      4. Return normalised result dict.
    """
    tmp_path: Optional[str] = None
    back_tmp_path: Optional[str] = None
    try:
        loop = asyncio.get_event_loop()

        tmp_path = await _prepare_image(image_data)
        tmp_path = await loop.run_in_executor(None, _resize_if_needed, tmp_path)
        logger.info("Front image ready: %s", tmp_path)

        if back_image_data:
            back_tmp_path = await _prepare_image(back_image_data)
            back_tmp_path = await loop.run_in_executor(None, _resize_if_needed, back_tmp_path)
            logger.info("Back image ready: %s", back_tmp_path)

        # Build ordered list: front first, back second if provided
        image_paths = [p for p in [tmp_path, back_tmp_path] if p]
        logger.info("Running orchestrator with %d image(s)", len(image_paths))

        gps = {"lat": latitude, "lng": longitude, "accuracy": 10.0}

        result = await loop.run_in_executor(
            _executor,
            _run_orchestrator_sync,
            image_paths,
            nafdac_no,
            category,
            gps,
            purchase_channel,
        )

        result["has_back_image"] = back_tmp_path is not None
        result["image_count"] = len(image_paths)
        return result

    finally:
        for path in [tmp_path, back_tmp_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
