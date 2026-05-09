"""
OCR Extractor
Handles:
  - Running PaddleOCR on the product image
  - Two-pass NAFDAC extraction with safe OCR error correction
  - Parsing raw text blocks into structured metadata JSON

TWO-PASS NAFDAC EXTRACTION:
Pass 1: Strict pattern - digits only after letter prefix. No corrections.
Pass 2: Loose pattern + OCR digit/letter correction.
    Only fires if Pass 1 finds nothing or finds a number not in DB.
    Corrected number ONLY returned if retriever confirms it in DB.

 
SECURITY GUARANTEE:
  Correction never authenticates a fake product.
  AQ-999999 (fake) -> A2-999999 -> not in DB -> None -> FAKE
  AQ-106037 (real OCR misread) -> A2-106037 -> in DB -> AUTHENTIC

IMAGE FORMAT HANDLING:
  Mobile apps often send PNG with alpha channel (RGBA).
  All images go through _load_bgr() which safely strips alpha channels.

NOTE: This module was previously updated to EasyOCR by another developer.
  Reverted to PaddleOCR — EasyOCR failed to detect NAFDAC numbers reliably
  on Nigerian product labels (missed A8-4114 on Kelloggs left panel image).

"""
import os
import cv2
import numpy as np
import re
from paddleocr import PaddleOCR

from .config import (
    NAFDAC_IN_TEXT_PATTERN,
    NAFDAC_PATTERN,
    BATCH_IN_TEXT_PATTERN,
    EXPIRY_PATTERN,
    MANUFACTURER_IN_TEXT_PATTERN,
)

# Loose NAFDAC pattern — catches OCR misreads like AQ-106037
# ONLY used in Pass 2. Never for primary matching.
_NAFDAC_LOOSE_KEYWORD = re.compile(
    r"(?:NAFDAC\s*(?:REG(?:ISTRATION)?\s*)?(?:\.?\s*NO\.?|NUMBER)?\s*|"
    r"REG(?:ISTRATION)?\s*(?:NO\.?|NUMBER)\s*)"
    r"[:\s]*([A-Z][A-Z0-9]{0,2}-[A-Z0-9]{3,6})",
    re.IGNORECASE
) 
_NAFDAC_LOOSE_STANDALONE = re.compile(r"\b[A-Z][A-Z0-9]{0,1}-[A-Z0-9]{3,6}\b")

# OCR digit/letter confusion map.
# Applied ONLY to positions in NAFDAC numbers that must be digits.
# Position 0 (leading letter) is NEVER corrected.
_DIGIT_CORRECTIONS = {
    "O": "0", "Q": "2", "I": "1",
    "S": "5", "B": "8", "G": "6", "Z": "2",
}

# PaddleOCR singleton — loaded once, reused across all scans
_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
    return _ocr_engine


# ==============================================================
# IMAGE LOADING 
# ==============================================================

def _load_bgr(image_path: str) -> np.ndarray:
    """Load image as 3-channel BGR, safe for PaddleOCR."""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(image_path)
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    elif img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


# ==============================================================
# OCR EXTRACTION
# ==============================================================

def extract_text_blocks(image_path: str) -> list:
    """
    Run PaddleOCR on the product image with bottom-crop fallback.
    If no NAFDAC found on full image, runs second pass on bottom 30% upscaled 2x.
    NAFDAC numbers on Nigerian product labels appear in small print at the bottom.
    """
    ocr_engine = get_ocr_engine()
    img = _load_bgr(image_path)

    # Primary pass — full image
    results = ocr_engine.ocr(img, cls=True)
    blocks  = _parse_paddle_results(results)
    full_text = " ".join(b["text"] for b in blocks)

    # Fallback pass — bottom 30% crop if no NAFDAC found
    if not _strict_nafdac_from_text(full_text):
        bottom = _crop_bottom(img, fraction=0.30, upscale=2.0)
        if bottom is not None:
            fallback_results = ocr_engine.ocr(bottom, cls=True)
            fallback_blocks  = _parse_paddle_results(fallback_results)
            existing = {b["text"] for b in blocks}
            for fb in fallback_blocks:
                if fb["text"] not in existing:
                    blocks.append(fb)
                    existing.add(fb["text"])

    return blocks


def _parse_paddle_results(results) -> list:
    """Parse PaddleOCR results into clean block dicts."""
    blocks = []
    if not results:
        return blocks
    for line in results:
        if not line:
            continue
        for item in line:
            if not item or len(item) < 2:
                continue
            text_info = item[1]
            if not text_info:
                continue
            text       = text_info[0].strip() if isinstance(text_info, (list, tuple)) else str(text_info).strip()
            confidence = float(text_info[1]) if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.5
            if text:
                blocks.append({"text": text, "confidence": round(confidence, 4)})
    return blocks


def _crop_bottom(img: np.ndarray, fraction: float = 0.30, upscale: float = 2.0):
    """Crop bottom fraction of image and upscale for better small-text OCR."""
    if img is None or img.size == 0:
        return None
    h, w  = img.shape[:2]
    y1    = int(h * (1.0 - fraction))
    crop  = img[y1:h, 0:w]
    new_h = int(crop.shape[0] * upscale)
    new_w = int(crop.shape[1] * upscale)
    return cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def build_raw_text(blocks: list) -> str:
    return " ".join(b["text"] for b in blocks)


#  NAFDAC extraction 

def _strict_nafdac_from_text(raw_text: str):
    """Strict extraction — digits only. Returns string or None."""
    match = NAFDAC_IN_TEXT_PATTERN.search(raw_text)
    if match:
        return match.group(1).upper()
    for token in raw_text.split():
        cleaned = token.strip(".,;:")
        if NAFDAC_PATTERN.match(cleaned.upper()):
            return cleaned.upper()
    return None


def _loose_nafdac_from_text(raw_text: str):
    """Loose extraction — may return misreads like AQ-106037."""
    match = _NAFDAC_LOOSE_KEYWORD.search(raw_text)
    if match:
        return match.group(1).upper()
    match = _NAFDAC_LOOSE_STANDALONE.search(raw_text)
    if match:
        return match.group().upper()
    return None


def _correct_ocr_errors(raw: str) -> str:
    """
    Fix OCR digit/letter confusion in NAFDAC number.
    Position 0 (leading letter) is NEVER changed.
    Only positions that MUST be digits are corrected.
    """
    if not raw or "-" not in raw:
        return raw
    prefix, suffix = raw.split("-", 1)
    prefix = list(prefix)
    suffix = list(suffix)
    for i in range(1, len(prefix)):
        prefix[i] = _DIGIT_CORRECTIONS.get(prefix[i], prefix[i])
    for i in range(len(suffix)):
        suffix[i] = _DIGIT_CORRECTIONS.get(suffix[i], suffix[i])
    return "".join(prefix) + "-" + "".join(suffix)


# ==============================================================
# NAFDAC EXTRACTION WITH SAFE CORRECTION
# ==============================================================

def extract_nafdac_number(raw_text: str, retriever=None):
    """
    Two-pass NAFDAC extraction with safe OCR error correction.

    Pass 1: Strict (digits only). Return if found in DB or no retriever.
    Pass 2: Loose + correction. Return ONLY if corrected number in DB.

    Security: Fake AQ-999999 -> A2-999999 -> not in DB -> None -> FAKE verdict.
              Real AQ-106037 -> A2-106037 -> in DB -> AUTHENTIC verdict.

    Args:
        raw_text:  Full OCR text.
        retriever: Optional ProductRetriever (orchestrator's shared singleton).
                   NEVER pass a newly instantiated retriever here.
    """
    #  Pass 1: strict 
    strict = _strict_nafdac_from_text(raw_text)

    if strict:
        if retriever is None:
            return strict
        if retriever.retrieve_by_nafdac_no(strict):
            return strict
        # In text but not in DB — fall through to Pass 2

    #  Pass 2: loose + correction 
    if retriever is None:
        return strict

    loose = _loose_nafdac_from_text(raw_text)
    if not loose:
        return strict

    corrected = _correct_ocr_errors(loose)
    if corrected == loose:
        return strict

    if retriever.retrieve_by_nafdac_no(corrected):
        return corrected   # confirmed in DB — safe to use

    return strict   # not confirmed — return original

#=============================================================
# INDIVIDUAL FIELD EXTRACTORS
# ==============================================================


def extract_batch_number(raw_text: str):
    """Find the batch/lot number in the label text."""
    match = BATCH_IN_TEXT_PATTERN.search(raw_text)
    return match.group(1).upper() if match else None


def extract_expiry_date(raw_text: str):
    """
    Find the expiry date using common date formats.
    Handles: 12/2026, 12-2026, DEC 2026, DEC. 2026
    """
    match = EXPIRY_PATTERN.search(raw_text)
    return match.group(0).strip() if match else None


def extract_product_name(blocks: list):
    """
    Identify the product name from OCR blocks.
    Highest-confidence block that is not purely numeric and has > 2 chars.
    """
    candidates = [
        b for b in blocks
        if not b["text"].isdigit() and len(b["text"]) > 2
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates[0]["text"]


def extract_manufacturer_name(raw_text: str):
    """Find the manufacturer/distributor name using common label keywords."""
    match = MANUFACTURER_IN_TEXT_PATTERN.search(raw_text)
    return match.group(1).strip() if match else None

def extract_volume(raw_text: str):
    match = re.search(r"\b\d+\s?(ml|g|kg|litre|l)\b", raw_text, re.IGNORECASE)
    return match.group().strip() if match else None

# ==============================================================
# METADATA BUILDER
# ==============================================================

def build_metadata(blocks: list, retriever=None) -> dict:
    """
    Combine all field extractors into structured metadata.

    Args:
        blocks:    OCR text blocks from extract_text_blocks().
        retriever: Optional ProductRetriever (orchestrator's shared instance).
                   Enables two-pass NAFDAC correction. Never instantiate new one here.
    """
    raw_text = build_raw_text(blocks)

    avg_confidence = (
        round(sum(b["confidence"] for b in blocks) / len(blocks), 4)
        if blocks else 0.0
    )

    strict     = _strict_nafdac_from_text(raw_text)
    nafdac_num = extract_nafdac_number(raw_text, retriever)
    was_corrected = (nafdac_num is not None and strict != nafdac_num)

    return {
        "product_name":         extract_product_name(blocks),
        "nafdac_number":        nafdac_num,
        "batch_number":         extract_batch_number(raw_text),
        "expiry_date":          extract_expiry_date(raw_text),
        "manufacturer_name":    extract_manufacturer_name(raw_text),
        "net_weight_or_volume": extract_volume(raw_text),
        "raw_ocr_text":         raw_text,
        "avg_ocr_confidence":   avg_confidence,
        "valid_format":         bool(nafdac_num and extract_batch_number(raw_text)),
        "nafdac_ocr_corrected": was_corrected,
    }