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

# ── Singleton orchestrator ────────────────────────────────────────────────────
_orchestrator = None
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-worker")


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
    """Write a base64 data-URL image to a temp file and return the path."""
    header, encoded = data_url.split(",", 1)
    suffix = ".png" if "png" in header else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(base64.b64decode(encoded))
    tmp.close()
    return tmp.name


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
    side_image_data: Optional[str] = None,
    detail_image_data: Optional[str] = None,
    nafdac_no: str = "",
    category: str = "unknown",
    latitude: float = 0.0,
    longitude: float = 0.0,
    purchase_channel: str = "unknown",
) -> dict:
    """
    Full scan pipeline:
      1. Save/download up to 4 images to temp files.
      2. Run ScanOrchestrator in a thread pool (non-blocking) with all image paths.
      3. Clean up temp files.
      4. Return normalised result dict.
    """
    tmp_path: Optional[str] = None
    back_tmp_path: Optional[str] = None
    side_tmp_path: Optional[str] = None
    detail_tmp_path: Optional[str] = None
    try:
        tmp_path = await _prepare_image(image_data)
        logger.info("Front image saved to %s", tmp_path)

        if back_image_data:
            back_tmp_path = await _prepare_image(back_image_data)
            logger.info("Back image saved to %s", back_tmp_path)

        if side_image_data:
            side_tmp_path = await _prepare_image(side_image_data)
            logger.info("Side image saved to %s", side_tmp_path)

        if detail_image_data:
            detail_tmp_path = await _prepare_image(detail_image_data)
            logger.info("Detail image saved to %s", detail_tmp_path)

        # Build ordered list: front is always first (primary)
        image_paths = [p for p in [tmp_path, back_tmp_path, side_tmp_path, detail_tmp_path] if p]
        logger.info("Running orchestrator with %d image(s)", len(image_paths))

        gps = {"lat": latitude, "lng": longitude, "accuracy": 10.0}

        loop = asyncio.get_event_loop()
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
        for path in [tmp_path, back_tmp_path, side_tmp_path, detail_tmp_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
