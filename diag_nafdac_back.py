"""
Diagnostic: Why is A8-2361 not extracted from Kelloggs_coco_pops_360g_back.jpg?

Checks:
  1. Raw image dimensions
  2. Full-image OCR - all blocks, raw text
  3. A8-2361 presence (exact + near-miss regex)
  4. NAFDAC_IN_TEXT_PATTERN match on raw text
  5. Standalone NAFDAC_PATTERN match on each block
  6. Bottom-30% crop OCR
  7. Rotated (90/180/270) full-image OCR
  8. Contrast/brightness stats on bounding region near "NAFDAC" keyword
"""

import sys
import os
import re

# ASCII-only output - no Unicode box-drawing or special chars

REPO_ROOT = r"C:\Dev\sabilens"
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ai_engine"))

IMAGE_PATH = os.path.join(
    REPO_ROOT, "product_images", "authentic_products",
    "Kelloggs_coco_pops_360g_back.jpg"
)

print("=== NAFDAC DIAGNOSTIC: Kelloggs_coco_pops_360g_back.jpg ===")
print()

import cv2
import numpy as np

# ---------------------------------------------------------------
# 1. Image dimensions
# ---------------------------------------------------------------
print("[1] IMAGE DIMENSIONS")
img = cv2.imread(IMAGE_PATH, cv2.IMREAD_UNCHANGED)
if img is None:
    print("    ERROR: Could not load image at:", IMAGE_PATH)
    sys.exit(1)

h, w = img.shape[:2]
channels = img.shape[2] if img.ndim == 3 else 1
print("    Path:     ", IMAGE_PATH)
print("    Dims:     ", w, "x", h, "px, channels:", channels)
print("    File size:", round(os.path.getsize(IMAGE_PATH) / 1024 / 1024, 2), "MB")
print()

# Ensure BGR for OCR
if channels == 4:
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
elif channels == 1:
    img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
else:
    img_bgr = img.copy()

# ---------------------------------------------------------------
# 2. Init OCR engine
# ---------------------------------------------------------------
print("[2] LOADING PaddleOCR (may take ~20s first run)...")
import logging
logging.disable(logging.CRITICAL)
from paddleocr import PaddleOCR
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
logging.disable(logging.NOTSET)
print("    OCR engine ready.")
print()

# ---------------------------------------------------------------
# Helper: run OCR and return list of (text, conf) tuples
# ---------------------------------------------------------------
def run_ocr(img_array):
    results = ocr_engine.ocr(img_array, cls=True)
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
            if isinstance(text_info, (list, tuple)):
                text = text_info[0].strip() if text_info[0] else ""
                conf = float(text_info[1]) if len(text_info) > 1 else 0.5
            else:
                text = str(text_info).strip()
                conf = 0.5
            if text:
                blocks.append((text, round(conf, 4)))
    return blocks

# ---------------------------------------------------------------
# 3. Full-image OCR
# ---------------------------------------------------------------
print("[3] FULL-IMAGE OCR")
full_blocks = run_ocr(img_bgr)
full_text = " ".join(b[0] for b in full_blocks)
print("    Total blocks:", len(full_blocks))
print("    Full raw text preview (first 600 chars):")
print("   ", full_text[:600])
print()

# ---------------------------------------------------------------
# 4. Search for A8-2361 exact + near-miss
# ---------------------------------------------------------------
print("[4] TARGET STRING SEARCH: A8-2361")
target = "A8-2361"
target_norm = target.upper()

exact_found = target_norm in full_text.upper()
print("    Exact 'A8-2361' in full_text:", "YES" if exact_found else "NO")

# Near-miss: any token starting with A8 or matching A[0-9]-[0-9]
near_miss_re = re.compile(r"\bA8[-\s]?\d{3,6}\b", re.IGNORECASE)
near_hits = near_miss_re.findall(full_text)
print("    Near-miss (A8-NNNN):", near_hits if near_hits else "NONE")

# Broader: anything that looks like A?-2361
part_re = re.compile(r"\b[A-Z]\d?[-\s]?2361\b", re.IGNORECASE)
part_hits = part_re.findall(full_text)
print("    Partial '?-2361':", part_hits if part_hits else "NONE")

# Broader still: just "2361" anywhere
plain_hits = re.findall(r"2361", full_text)
print("    Plain '2361' anywhere:", plain_hits if plain_hits else "NONE")

# Search "A8" anywhere
a8_hits = re.findall(r"\bA8\b", full_text, re.IGNORECASE)
print("    'A8' standalone:", a8_hits if a8_hits else "NONE")
print()

# ---------------------------------------------------------------
# 5. NAFDAC keyword + pattern search
# ---------------------------------------------------------------
print("[5] NAFDAC KEYWORD SEARCH IN RAW BLOCKS")
nafdac_keyword_re = re.compile(r"NAFDAC|REG\s*NO|REGISTRATION", re.IGNORECASE)
nafdac_pattern_re = re.compile(r"^[A-Z0-9]{1,3}-\d{3,6}$")

keyword_blocks = [(t, c) for t, c in full_blocks if nafdac_keyword_re.search(t)]
standalone_nafdac = [(t, c) for t, c in full_blocks if nafdac_pattern_re.match(t.strip().upper())]

print("    Blocks with NAFDAC/REG NO keyword:", len(keyword_blocks))
for t, c in keyword_blocks:
    print("       conf={:.4f}  text='{}'".format(c, t))

print("    Blocks matching standalone NAFDAC format (XX-NNNNN):", len(standalone_nafdac))
for t, c in standalone_nafdac:
    print("       conf={:.4f}  text='{}'".format(c, t))

# Apply NAFDAC_IN_TEXT_PATTERN from config
from ai_engine.ocr_linguistic.config import NAFDAC_IN_TEXT_PATTERN, NAFDAC_PATTERN
m = NAFDAC_IN_TEXT_PATTERN.search(full_text)
print()
print("    NAFDAC_IN_TEXT_PATTERN match on full text:", m.group(1) if m else "NONE")
print()

# ---------------------------------------------------------------
# 6. All blocks dump (sorted by confidence desc) - show top 40
# ---------------------------------------------------------------
print("[6] ALL OCR BLOCKS (top 40 by confidence)")
sorted_blocks = sorted(full_blocks, key=lambda x: x[1], reverse=True)
for i, (t, c) in enumerate(sorted_blocks[:40]):
    print("    {:2d}. conf={:.4f}  '{}'".format(i+1, c, t))
print()

# ---------------------------------------------------------------
# 7. Bottom-30% crop OCR
# ---------------------------------------------------------------
print("[7] BOTTOM-30% CROP OCR")
y1 = int(h * 0.70)
crop_bottom = img_bgr[y1:h, 0:w]
crop_h, crop_w = crop_bottom.shape[:2]
print("    Crop region: y={} to y={}, size={}x{}".format(y1, h, crop_w, crop_h))

# upscale 2x
up_h = int(crop_h * 2)
up_w = int(crop_w * 2)
crop_up = cv2.resize(crop_bottom, (up_w, up_h), interpolation=cv2.INTER_CUBIC)
bottom_blocks = run_ocr(crop_up)
bottom_text = " ".join(b[0] for b in bottom_blocks)
print("    Bottom crop total blocks:", len(bottom_blocks))
print("    Bottom crop text (full):")
print("   ", bottom_text)

exact_in_bottom = target_norm in bottom_text.upper()
print()
print("    A8-2361 in bottom crop:", "YES" if exact_in_bottom else "NO")
nafdac_in_bottom = [(t, c) for t, c in bottom_blocks if nafdac_pattern_re.match(t.strip().upper())]
print("    Standalone NAFDAC format in bottom crop:", nafdac_in_bottom if nafdac_in_bottom else "NONE")
m2 = NAFDAC_IN_TEXT_PATTERN.search(bottom_text)
print("    NAFDAC_IN_TEXT_PATTERN in bottom text:", m2.group(1) if m2 else "NONE")
print()

# ---------------------------------------------------------------
# 8. Top-30% crop (NAFDAC sometimes at top)
# ---------------------------------------------------------------
print("[8] TOP-30% CROP OCR")
y_end = int(h * 0.30)
crop_top = img_bgr[0:y_end, 0:w]
up_top = cv2.resize(crop_top, (crop_top.shape[1]*2, crop_top.shape[0]*2), interpolation=cv2.INTER_CUBIC)
top_blocks = run_ocr(up_top)
top_text = " ".join(b[0] for b in top_blocks)
print("    Top crop total blocks:", len(top_blocks))
exact_in_top = target_norm in top_text.upper()
print("    A8-2361 in top crop:", "YES" if exact_in_top else "NO")
nafdac_in_top = [(t, c) for t, c in top_blocks if nafdac_pattern_re.match(t.strip().upper())]
print("    Standalone NAFDAC format in top crop:", nafdac_in_top if nafdac_in_top else "NONE")
m3 = NAFDAC_IN_TEXT_PATTERN.search(top_text)
print("    NAFDAC_IN_TEXT_PATTERN in top text:", m3.group(1) if m3 else "NONE")
print()

# ---------------------------------------------------------------
# 9. Rotated-image OCR (90, 180, 270 degrees)
# ---------------------------------------------------------------
print("[9] ROTATED IMAGE OCR")
rotations = {
    "90_CW":  cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE),
    "180":    cv2.rotate(img_bgr, cv2.ROTATE_180),
    "90_CCW": cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE),
}
for rot_name, rot_img in rotations.items():
    rot_blocks = run_ocr(rot_img)
    rot_text = " ".join(b[0] for b in rot_blocks)
    found = target_norm in rot_text.upper()
    standalone = [(t, c) for t, c in rot_blocks if nafdac_pattern_re.match(t.strip().upper())]
    m_r = NAFDAC_IN_TEXT_PATTERN.search(rot_text)
    print("    Rotation {}:  A8-2361 found={}, standalone NAFDAC={}, keyword match={}".format(
        rot_name, found,
        [t for t, c in standalone] if standalone else "NONE",
        m_r.group(1) if m_r else "NONE"
    ))
print()

# ---------------------------------------------------------------
# 10. Near-NAFDAC context: show blocks around any "NAFDAC" keyword
# ---------------------------------------------------------------
print("[10] CONTEXT AROUND NAFDAC KEYWORD BLOCKS")
for i, (t, c) in enumerate(full_blocks):
    if nafdac_keyword_re.search(t):
        start = max(0, i - 3)
        end   = min(len(full_blocks), i + 5)
        print("    Context window around block {}:".format(i))
        for j in range(start, end):
            marker = ">>>" if j == i else "   "
            print("    {} [{:2d}] conf={:.4f}  '{}'".format(
                marker, j, full_blocks[j][1], full_blocks[j][0]))
        print()

# ---------------------------------------------------------------
# 11. Loose NAFDAC patterns (from extractor.py)
# ---------------------------------------------------------------
print("[11] LOOSE PATTERN MATCHES")
loose_kw = re.compile(
    r"(?:NAFDAC\s*(?:REG(?:ISTRATION)?\s*)?(?:\.?\s*NO\.?|NUMBER)?\s*|"
    r"REG(?:ISTRATION)?\s*(?:NO\.?|NUMBER)\s*)"
    r"[:\s]*([A-Z][A-Z0-9]{0,2}-[A-Z0-9]{3,6})",
    re.IGNORECASE
)
loose_standalone = re.compile(r"\b[A-Z][A-Z0-9]{0,1}-[A-Z0-9]{3,6}\b")

m_lk = loose_kw.search(full_text)
m_ls = loose_standalone.findall(full_text)
print("    Loose keyword match:", m_lk.group(1) if m_lk else "NONE")
print("    Loose standalone matches:", m_ls if m_ls else "NONE")
print()

# ---------------------------------------------------------------
# 12. Summary
# ---------------------------------------------------------------
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print("Image:       ", os.path.basename(IMAGE_PATH))
print("Dimensions:  ", w, "x", h)
print("OCR blocks:  ", len(full_blocks))
print("A8-2361 in full OCR: ", "YES" if exact_found else "NO")
print("A8-2361 in bottom 30%:", "YES" if exact_in_bottom else "NO")
print("A8-2361 in top 30%:  ", "YES" if exact_in_top else "NO")
print("Keyword match (strict):", m.group(1) if m else "NONE")
print("Keyword match (loose): ", m_lk.group(1) if m_lk else "NONE")
print("Standalone loose hits: ", m_ls[:10] if m_ls else "NONE")
print()
print("DONE.")
