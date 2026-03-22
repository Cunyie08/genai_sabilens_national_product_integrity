"""
OCR Extractor
Handles:
  - Running EasyOCR on the product image
  - Parsing raw text blocks into structured metadata JSON

NAFDAC FALLBACK STRATEGY:
  If the primary full-image OCR pass doesn't find a NAFDAC number,
  a second pass runs on a cropped + upscaled bottom 25% of the image.
  NAFDAC numbers on Nigerian product labels almost always appear in the
  bottom section in small print. Upscaling that region 2x gives the OCR
  engine a much better chance of reading it.



IMAGE FORMAT HANDLING:
  Mobile apps often send PNG images with an alpha channel (RGBA / 4-channel).
  EasyOCR's internal greyscale conversion does:
      maximum_y, maximum_x = img.shape   # fails for 3-channel arrays
  which raises ValueError: too many values to unpack.
  All image loading in this module goes through _load_bgr() which safely
  strips the alpha channel before passing the image to EasyOCR.
"""
import os
import tempfile
import cv2
import numpy as np
import easyocr
from .config import (
    NAFDAC_IN_TEXT_PATTERN,
    NAFDAC_PATTERN,
    BATCH_IN_TEXT_PATTERN,
    EXPIRY_PATTERN,
    MANUFACTURER_IN_TEXT_PATTERN,
)


# Initialize EasyOCR Reader once at module level (avoids reloading model repeatedly)
# gpu=False for CPU-only environments (Windows without CUDA)
_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_engine

# ==============================================================
# IMAGE LOADING HELPER
# ==============================================================

def _load_bgr(image_path: str) -> np.ndarray:
    """
    Load an image from disk as a 3-channel BGR array, safe for EasyOCR.

    Handles:
      - JPEG / JPG   : already 3-channel, no conversion needed
      - PNG (RGB)    : 3-channel, no conversion needed
      - PNG (RGBA)   : 4-channel — alpha stripped → 3-channel BGR
      - Greyscale    : 1-channel — promoted to 3-channel BGR

    Raises:
        ValueError: if the file cannot be read by OpenCV.
    """
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)

    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    # RGBA (4-channel) → BGR (3-channel): drop the alpha channel
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    # Greyscale (1-channel) → BGR (3-channel): replicate across channels
    elif img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return img



# ==============================================================
# OCR EXTRACTION
# ==============================================================

def extract_text_blocks(image_path: str) -> list[dict]:
    """
    Run PaddleOCR on the product image.
    If no NAFDAC number is found in the full-image pass, runs a second
    pass on the bottom 25% of the image (cropped + upscaled 2x).

    Args:
        image_path: File path to the product image (JPG, PNG, etc.)

    Returns:
        List of dicts, each with:
          - 'text': the detected string
          - 'confidence': float 0.0-1.0
    """

    
    ocr_engine = get_ocr_engine()

    # Primary pass: full image - pass numpy array directly, no temp file
    img = _load_bgr(image_path)
    results = ocr_engine.readtext(img)   # EasyOCR accepts numpy arrays directly
    blocks    = _parse_ocr_results(results)
    full_text = " ".join(b["text"] for b in blocks)
    nafdac    = extract_nafdac_number(full_text)

    if nafdac:
        return blocks

    # Fallback pass: bottom 30% crop
    bottom_crop = _crop_bottom(img, fraction=0.30, upscale=2.0)
    if bottom_crop is not None:
        fallback_results = ocr_engine.readtext(bottom_crop)
        fallback_blocks  = _parse_ocr_results(fallback_results)
        existing_texts = {b["text"] for b in blocks}
        for fb in fallback_blocks:
            if fb["text"] not in existing_texts:
                blocks.append(fb)
                existing_texts.add(fb["text"])

    return blocks

def _parse_ocr_results(results) -> list:
    """Parse raw EasyOCR results into clean block dicts.
    EasyOCR returns: [(bbox, text, confidence), ...]
    """
    blocks = []
    if not results:
        return blocks
    for item in results:
        text       = item[1].strip()
        confidence = round(float(item[2]), 4)
        if text:
            blocks.append({"text": text, "confidence": confidence})
    return blocks

def _crop_bottom(img: np.ndarray, fraction: float = 0.30, upscale: float = 2.0):
    """
    Crop the bottom `fraction` of the image and upscale it.

    Args:
        image_path: Path to the image file.
        fraction:   Fraction of image height to crop from bottom (0.30 = bottom 30%).
        upscale:    Scale factor for upscaling the crop.

    Returns:
        Upscaled BGR numpy array ready for EasyOCR, or None if img is invalid.
    """
    if img is None or img.size == 0:
        return None

    h, w  = img.shape[:2]
    y1    = int(h * (1.0 - fraction))
    crop  = img[y1:h, 0:w]

    new_h    = int(crop.shape[0] * upscale)
    new_w    = int(crop.shape[1] * upscale)
    upscaled = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return upscaled


def build_raw_text(blocks: list) -> str:
    """Join all text blocks into a single string for regex matching."""
    return " ".join(b["text"] for b in blocks)


# ==============================================================
# INDIVIDUAL FIELD EXTRACTORS
# ==============================================================

def extract_nafdac_number(raw_text: str) -> str | None:
    """
    Find the NAFDAC registration number in the label text.
    Tries keyword-based match first, falls back to format match.
    """
    # Primary: look for NAFDAC/REG keyword followed by the number
    match = NAFDAC_IN_TEXT_PATTERN.search(raw_text)
    if match:
        return match.group(1).upper()

    # Fallback: scan each token for NAFDAC number format
    for token in raw_text.split():
        cleaned = token.strip(".,;:")
        if NAFDAC_PATTERN.match(cleaned.upper()):
            return cleaned.upper()

    return None


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


# ==============================================================
# METADATA BUILDER
# ==============================================================

def build_metadata(blocks: list) -> dict:
    """
    Combine all field extractors into one structured metadata dict.

    Args:
        blocks: List of OCR text blocks from extract_text_blocks()

    Returns:
        Structured metadata dict ready for linguistic validation.
    """
    raw_text = build_raw_text(blocks)

    avg_confidence = (
        round(sum(b["confidence"] for b in blocks) / len(blocks), 4)
        if blocks else 0.0
    )

    return {
        "product_name":      extract_product_name(blocks),
        "nafdac_number":     extract_nafdac_number(raw_text),
        "batch_number":      extract_batch_number(raw_text),
        "expiry_date":       extract_expiry_date(raw_text),
        "manufacturer_name": extract_manufacturer_name(raw_text),
        "raw_ocr_text":      raw_text,
        "avg_ocr_confidence": avg_confidence,
    }