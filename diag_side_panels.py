"""
Diagnostic: Which side panel of genuine Kelloggs Coco Pops carries A8-2361?
Tests left and right panel images from authentic_products folder.
ASCII-only output -- no Unicode chars.
"""
import sys
import os
import re

REPO_ROOT = r"C:\Dev\sabilens"
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ai_engine"))

import logging
logging.disable(logging.CRITICAL)

import cv2
import numpy as np

from paddleocr import PaddleOCR
from ai_engine.ocr_linguistic.config import NAFDAC_IN_TEXT_PATTERN, NAFDAC_PATTERN
from ai_engine.ocr_linguistic.extractor import (
    _strict_nafdac_from_text,
    _loose_nafdac_from_text,
)

logging.disable(logging.NOTSET)

IMAGES = [
    r"C:\Dev\sabilens\product_images\authentic_products\Kelloggs_coco_pops_360g_left.jpg",
    r"C:\Dev\sabilens\product_images\authentic_products\Kelloggs_coco_pops_360g_right.jpg",
]

# Near-miss patterns for A8-2361
TARGET_EXACT = re.compile(r"A8[-\s]?2361", re.IGNORECASE)
TARGET_NEARMISS = re.compile(
    r"(?:A8[-\s]?236I|AB[-\s]?2361|48[-\s]?2361|A82361|[A-Z][0-9][-\s]?2361)",
    re.IGNORECASE,
)
TARGET_FRAGMENT = re.compile(r"2361")
NAFDAC_KW = re.compile(r"NAFDAC|REG\s*NO|REGISTRATION", re.IGNORECASE)
STANDALONE_FMT = re.compile(r"^[A-Z0-9]{1,3}-\d{3,6}$")

print("Loading PaddleOCR engine...")
_ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
print("Engine ready.")
print()


def run_ocr(img_array):
    logging.disable(logging.CRITICAL)
    results = _ocr.ocr(img_array, cls=True)
    logging.disable(logging.NOTSET)
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


def search_target(blocks, label):
    raw_text = " ".join(t for t, c in blocks)
    exact = TARGET_EXACT.search(raw_text)
    nearmiss = TARGET_NEARMISS.search(raw_text)
    fragment = TARGET_FRAGMENT.search(raw_text)
    kw = NAFDAC_KW.search(raw_text)

    hit_blocks_exact = [(t, c) for t, c in blocks if TARGET_EXACT.search(t)]
    hit_blocks_near  = [(t, c) for t, c in blocks if TARGET_NEARMISS.search(t)]
    hit_blocks_frag  = [(t, c) for t, c in blocks if TARGET_FRAGMENT.search(t)]
    kw_blocks        = [(t, c) for t, c in blocks if NAFDAC_KW.search(t)]
    standalone       = [(t, c) for t, c in blocks if STANDALONE_FMT.match(t.strip().upper())]

    print("  [{}] total blocks: {}".format(label, len(blocks)))
    print("  A8-2361 exact in raw text:    {}".format("YES" if exact else "NO"))
    print("  Near-miss in raw text:        {}".format("YES" if nearmiss else "NO"))
    print("  Fragment '2361' in raw text:  {}".format("YES" if fragment else "NO"))
    print("  NAFDAC keyword present:       {}".format("YES" if kw else "NO"))

    if hit_blocks_exact:
        print("  -- EXACT MATCH blocks:")
        for t, c in hit_blocks_exact:
            print("     conf={:.4f}  text='{}'".format(c, t))
    if hit_blocks_near:
        print("  -- NEAR-MISS blocks:")
        for t, c in hit_blocks_near:
            print("     conf={:.4f}  text='{}'".format(c, t))
    if hit_blocks_frag:
        print("  -- FRAGMENT '2361' blocks:")
        for t, c in hit_blocks_frag:
            print("     conf={:.4f}  text='{}'".format(c, t))
    if kw_blocks:
        print("  -- NAFDAC keyword blocks:")
        for t, c in kw_blocks:
            print("     conf={:.4f}  text='{}'".format(c, t))
    if standalone:
        print("  -- STANDALONE NAFDAC-format blocks:")
        for t, c in standalone:
            print("     conf={:.4f}  text='{}'".format(c, t))

    return bool(exact), bool(nearmiss or fragment), raw_text


for image_path in IMAGES:
    label = os.path.basename(image_path)
    print("=" * 60)
    print("IMAGE: {}".format(label))
    print("FOLDER: authentic_products")
    print("=" * 60)

    # ---- STEP 1: file check ----
    print()
    print("STEP 1 -- File info")
    exists = os.path.isfile(image_path)
    print("  Full path:  {}".format(image_path))
    print("  Exists:     {}".format("YES" if exists else "NO"))
    if not exists:
        print("  SKIPPING -- file not found.")
        print()
        continue

    size_mb = round(os.path.getsize(image_path) / 1024 / 1024, 2)
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print("  ERROR: cv2 could not load image.")
        print()
        continue
    h, w = img.shape[:2]
    ch = img.shape[2] if img.ndim == 3 else 1
    print("  File size:  {} MB".format(size_mb))
    print("  Dimensions: {} x {} px, {} channels".format(w, h, ch))

    # Normalise to BGR
    if ch == 4:
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    elif ch == 1:
        img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        img_bgr = img.copy()

    # ---- STEP 2: full-image OCR ----
    print()
    print("STEP 2 -- Full-image OCR")
    full_blocks = run_ocr(img_bgr)
    full_text = " ".join(t for t, c in full_blocks)

    print("  All blocks (sorted by confidence desc):")
    for i, (t, c) in enumerate(sorted(full_blocks, key=lambda x: x[1], reverse=True)):
        print("    {:2d}. conf={:.4f}  '{}'".format(i+1, c, t))

    print()
    exact_found, near_found, _ = search_target(full_blocks, "full-image")

    strict_result = _strict_nafdac_from_text(full_text)
    loose_result  = _loose_nafdac_from_text(full_text)
    print()
    print("  _strict_nafdac_from_text: {}".format(strict_result if strict_result else "NONE"))
    print("  _loose_nafdac_from_text:  {}".format(loose_result  if loose_result  else "NONE"))

    # ---- STEP 3: rotations + upscale (only if not found yet) ----
    found_via = None
    if exact_found:
        found_via = "full-image (upright)"

    if not found_via:
        print()
        print("STEP 3 -- Rotations + upscale (A8-2361 not found upright)")

        rotations = [
            ("90_CW",  cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)),
            ("180",    cv2.rotate(img_bgr, cv2.ROTATE_180)),
            ("90_CCW", cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)),
        ]
        for rot_name, rot_img in rotations:
            rot_blocks = run_ocr(rot_img)
            rot_text   = " ".join(t for t, c in rot_blocks)
            e = TARGET_EXACT.search(rot_text)
            n = TARGET_NEARMISS.search(rot_text)
            f = TARGET_FRAGMENT.search(rot_text)
            standalone_r = [(t, c) for t, c in rot_blocks if STANDALONE_FMT.match(t.strip().upper())]
            print("  Rotation {}: exact={} near={} fragment={} standalone={}".format(
                rot_name,
                "YES" if e else "NO",
                "YES" if n else "NO",
                "YES" if f else "NO",
                [t for t, c in standalone_r] if standalone_r else "NONE",
            ))
            if e and not found_via:
                found_via = "rotation {}".format(rot_name)
                hit = TARGET_EXACT.search(rot_text)
                print("    >> FOUND via rotation {}: '{}'".format(rot_name, hit.group(0)))
                strict_r = _strict_nafdac_from_text(rot_text)
                loose_r  = _loose_nafdac_from_text(rot_text)
                print("    >> _strict after rotation: {}".format(strict_r if strict_r else "NONE"))
                print("    >> _loose  after rotation: {}".format(loose_r  if loose_r  else "NONE"))

        # 2x upscale
        up_h = int(h * 2)
        up_w = int(w * 2)
        img_up = cv2.resize(img_bgr, (up_w, up_h), interpolation=cv2.INTER_CUBIC)
        up_blocks = run_ocr(img_up)
        up_text   = " ".join(t for t, c in up_blocks)
        eu = TARGET_EXACT.search(up_text)
        nu = TARGET_NEARMISS.search(up_text)
        fu = TARGET_FRAGMENT.search(up_text)
        standalone_u = [(t, c) for t, c in up_blocks if STANDALONE_FMT.match(t.strip().upper())]
        print("  2x upscale:   exact={} near={} fragment={} standalone={}".format(
            "YES" if eu else "NO",
            "YES" if nu else "NO",
            "YES" if fu else "NO",
            [t for t, c in standalone_u] if standalone_u else "NONE",
        ))
        if eu and not found_via:
            found_via = "2x upscale"
            print("    >> FOUND via 2x upscale")
            strict_u = _strict_nafdac_from_text(up_text)
            loose_u  = _loose_nafdac_from_text(up_text)
            print("    >> _strict after upscale: {}".format(strict_u if strict_u else "NONE"))
            print("    >> _loose  after upscale: {}".format(loose_u  if loose_u  else "NONE"))
        elif (nu or fu) and not found_via:
            # Report near-miss/fragment blocks even if exact not found
            for t, c in up_blocks:
                if TARGET_NEARMISS.search(t) or TARGET_FRAGMENT.search(t):
                    print("    >> near/fragment in upscale: conf={:.4f}  '{}'".format(c, t))

    # ---- STEP 4: verdict ----
    print()
    print("STEP 4 -- VERDICT for {}".format(label))
    if exact_found or found_via:
        strict_check = _strict_nafdac_from_text(full_text)
        loose_check  = _loose_nafdac_from_text(full_text)
        extracted = strict_check == "A8-2361" or loose_check == "A8-2361"
        if extracted:
            print("  VERDICT: A8-2361 PRESENT and EXTRACTED")
            print("  Found via: {}".format(found_via or "full-image (upright)"))
        else:
            print("  VERDICT: A8-2361 PRESENT but NOT EXTRACTED")
            print("  Found via: {}".format(found_via or "full-image (upright)"))
            # Show which block has it so format mismatch is visible
            for t, c in full_blocks:
                if TARGET_EXACT.search(t) or TARGET_NEARMISS.search(t):
                    print("  OCR block text (exact string): '{}'  conf={:.4f}".format(t, c))
    else:
        print("  VERDICT: A8-2361 NOT PRESENT in this image at all")
        print("  (no exact match, no near-miss, no '2361' fragment in any orientation)")

    print()

print("=" * 60)
print("DONE")
