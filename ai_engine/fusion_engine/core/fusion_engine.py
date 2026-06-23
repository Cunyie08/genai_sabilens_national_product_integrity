"""
This file contains the Core brain of Fusion. Receives three adapted signals from the adapters,
selects the correct weight set, applies overrides, and produces
a single weighted authenticity verdict.

CALL ORDER IN PIPELINE:
  visual_adapter.adapt()  :  visual_signal
  ocr_adapter.adapt()     :  ocr_signal
  reg_adapter.adapt()     :  reg_signal
                          :  run_fusion(visual, ocr, reg)  ← THIS FILE

SCORE SCALE: 0.0 - 1.0 throughout. Aligned to orchestrator/pipeline.py.

WEIGHT SELECTION (Step 1 - before any scoring):
  _resolve_weights() picks ONE weight set based on scan quality and REG path.

  ┌──────────────────────────────────────────────────────────────────────┐
  │ SPECIAL CASE - RESCAN_REQUIRED (no scoring, no verdict)              │
  │   damage_score >= 0.8 AND blur_value < EXTREME_BLUR_CEILING (5.0)    │
  │   Image is too degraded. Scan rejected. Image saved for retraining.  │
  │   NEVER returns FAKE for a bad photo.                                │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Mode DAMAGED  - damage_score >= DAMAGED_SCORE_FLOOR (0.4)            │
  │   Visual is blur-compromised. Regulatory takes authority.            |         │
  │   Applies even if REG used semantic fallback.                        │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Mode FALLBACK - damage_score < 0.4 AND fallback_used=True            │
  │   Image is sharp but Regulatory used semantic search.                        │
  │   Regulatory is uncertain. Visual and OCR lead.                      |            │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Mode BASE     - damage_score < 0.4 AND fallback_used=False           │
  │   Best case. Sharp image, exact NAFDAC match. Visual leads.          |        │
  └──────────────────────────────────────────────────────────────────────┘

OVERRIDE HIERARCHY (Step 2 - after weight selection, before scoring):
  Priority 1 - Regulatory CRITICAL status -> force FAKE (score=0.0)
    Triggered by: AGENT_ERROR, EXPIRED
    NOT_FOUND is NOT a hard override — it is a DB coverage gap (see reg_adapter.py).
  Priority 2 - Visual logo too low OR OCR no NAFDAC -> floor SUSPICIOUS (score=0.45)
    Only fires if weighted score would have been AUTHENTIC (>= 0.75).
    Does NOT fire if Regulatory override already fired.

DAMAGE IS NOT AN OVERRIDE:
  damage_score and blur_value only affect weight selection.
  A blurry photo of a real product is never forced to FAKE.
  It is SUSPICIOUS at worst, and only if other signals also fail.

FUSION FORMULA:
  final_score = (visual_score x w1) + (ocr_score x w2) + (reg_score × w3)
  where w1 + w2 + w3 = 1.0 from the selected weight set.

SCORE -> VERDICT (Step 3):
  >= 0.75 -> AUTHENTIC   (severity: NONE)
  0.45-0.74-> SUSPICIOUS  (severity: MEDIUM)
  < 0.45  -> FAKE        (severity: CRITICAL)

SCALABILITY NOTES:
  - Add new weight modes in config/weights.py and extend _resolve_weights() here.
  - Add new override types by extending the override hierarchy in run_fusion().
  - Add new warning types in _build_warnings().
  - Never import Visual/OCR/Regulatory modules here - this file receives adapted signals only.
"""

import re
import difflib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Minimum character-similarity ratio for two product names to be considered the same.
# "Coco Pops" vs "Cocoa Pups" scores ~0.82 (below → MISMATCH).
# "COCO POPS" vs "Coco Pops" resolves via exact/substring check first (→ MATCH).
NAME_MATCH_THRESHOLD = 0.85

from ai_engine.fusion_engine.config.weights import (
    SIGNAL_WEIGHTS,
    SIGNAL_WEIGHTS_DAMAGED,
    SIGNAL_WEIGHTS_FALLBACK, 
)
from ai_engine.fusion_engine.config.thresholds import (
    get_verdict,
    get_severity,
    get_confidence_label,
    SUSPICIOUS_FLOOR_SCORE,
    EXTREME_BLUR_CEILING,
    DAMAGED_SCORE_FLOOR,
)


def run_fusion(visual_signal: dict, ocr_signal: dict, reg_signal: dict) -> dict:
    """
    Core fusion function. Receives three adapted signals, returns verdict.

    Args:
        visual_signal: Output of signals/visual_adapter.adapt()
        ocr_signal: Output of signals/ocr_adapter.adapt()
        reg_signal: Output of signals/reg_adapter.adapt()

    Returns:
        FusionResult dict consumed by decision_classifier.classify() and
        evidence_packager.package(). Contains verdict, score, breakdown,
        overrides, warnings, and all evidence fields needed downstream.

    Special return - RESCAN_REQUIRED:
        If blur_value < EXTREME_BLUR_CEILING and damage_score >= 0.8,
        returns a RESCAN_REQUIRED dict instead of a verdict dict.
        The image is flagged for saving. No NAFDAC report is generated.
    """

    # Early exit: no product detected in image
    if visual_signal.get("no_product_detected"):
        return {
            "verdict":          "INVALID_IMAGE",
            "final_score":      0.0,
            "severity":         "NONE",
            "confidence_label": "NONE",
            "rescan_required":  False,
            "weight_mode":      "REJECTED",
            "weights_used":     None,
            "retrieval_path":   None,
            "override_applied": True,
            "applied_override": {"source": "VISUAL", "type": "NO_PRODUCT_DETECTED", "reason": "NO_PRODUCT_DETECTED"},
            "all_overrides":    [],
            "breakdown":        {},
            "warnings":         [{"type": "NO_PRODUCT_DETECTED", "message": "Image does not contain a recognisable product label. Please take a clear photo of the product label and try again."}],
            "atlas_detail":     "",
            "atlas_summary":    "No product detected in image.",
            "evidence":         {"product_matched_visual": "NO_PRODUCT_DETECTED", "save_for_retraining": False, "save_reason": None},
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }

    # Extract scores (all 0.0-1.0, positive direction) 
    visual_score = float(visual_signal.get("fusion_score", 0.0))
    ocr_score = float(ocr_signal.get("fusion_score", 0.0))
    reg_score = float(reg_signal.get("fusion_score", 0.0))

    # Read scan quality and retrieval signals 
    damage_score   = float(visual_signal.get("damage_score",  0.1))
    blur_value     = float(visual_signal.get("blur_value",    60.0))
    retrieval_path         = reg_signal.get("retrieval_path",      "nafdac_exact")
    fallback_used          = bool(reg_signal.get("fallback_used",  False))
    nafdac_number          = ocr_signal.get("nafdac_number")
    ocr_product_name       = ocr_signal.get("product_name")
    visual_product_matched = visual_signal.get("product_matched")

    #  Extreme blur check - reject before fusion 
    # Never return FAKE for a bad photo. Reject the scan and save for retraining.
    if damage_score >= 0.8 and blur_value < EXTREME_BLUR_CEILING:
        return _build_rescan_required(
            blur_value   = blur_value,
            damage_score = damage_score,
            visual_signal    = visual_signal,
            ocr_signal    = ocr_signal,
        )

    # Select weight set
    weights, weight_mode = _resolve_weights(
        damage_score  = damage_score,
        fallback_used = fallback_used,
    )

    # Name/identity cross-validation — detects real NAFDAC number on fake packaging
    name_id_check = _check_name_identity(
        reg_signal             = reg_signal,
        ocr_product_name       = ocr_product_name,
        visual_product_matched = visual_product_matched,
    )

    # Collect all override flags
    overrides_triggered = []
    for signal, label in [
        (visual_signal, "VISUAL"),
        (ocr_signal, "OCR"),
        (reg_signal, "REG"),
    ]:
        if signal.get("override_flag"):
            overrides_triggered.append({
                "source": label,
                "reason": signal.get("override_reason", "Unknown override"),
            })

    # Evaluate override hierarchy
    forced_verdict   = None
    forced_score     = None
    applied_override = None

    # Priority 0 - Identity mismatch: NAFDAC verified but product name does not match.
    # Real NAFDAC number on mismatched packaging is the primary counterfeit vector.
    # This fires BEFORE the reg override so it is never masked by an EXPIRED/AGENT_ERROR.
    if name_id_check["mismatch_detected"]:
        forced_verdict   = "FAKE"
        forced_score     = 0.0
        applied_override = {
            "source": "NAME_MISMATCH",
            "type":   "IDENTITY_MISMATCH",
            "reason": name_id_check["reason"],
        }
        overrides_triggered.insert(0, {
            "source": "NAME_MISMATCH",
            "reason": name_id_check["reason"],
        })

    # Priority 1 - Regulatory CRITICAL -> force FAKE
    elif reg_signal.get("override_flag"):
        forced_verdict   = "FAKE"
        forced_score     = 0.0
        applied_override = {
            "source": "REG",
            "type":   "HARD_FAKE",
            "reason": reg_signal.get("override_reason"),
        }

    # Priority 2 - Visual logo too low OR OCR no NAFDAC -> floor SUSPICIOUS
    # Only fires if score would have been AUTHENTIC - avoids suppressing a FAKE verdict
    elif visual_signal.get("override_flag") or ocr_signal.get("override_flag"):
        raw_weighted = _compute_weighted(visual_score, ocr_score, reg_score, weights)
        if raw_weighted >= SUSPICIOUS_FLOOR_SCORE:
            source           = "VISUAL" if visual_signal.get("override_flag") else "OCR"
            forced_verdict   = "SUSPICIOUS"
            forced_score     = SUSPICIOUS_FLOOR_SCORE
            applied_override = {
                "source": source,
                "type":   "SUSPICIOUS_FLOOR",
                "reason": (
                    visual_signal.get("override_reason") or
                    ocr_signal.get("override_reason")
                ),
            }

    # Compute final score and verdict 
    if forced_score is not None:
        final_score = forced_score
        verdict     = forced_verdict
    else:
        final_score = _compute_weighted(visual_score, ocr_score, reg_score, weights)
        verdict     = get_verdict(final_score)

    severity         = get_severity(verdict)
    confidence_label = get_confidence_label(final_score)

    # Build score breakdown 
    breakdown = {
        "visual": {
            "raw_score":       visual_score,
            "weight":          weights["visual"],
            "weighted":        round(visual_score * weights["visual"], 4),
            "product_matched": visual_signal.get("product_matched"),
            "damage_score":    damage_score,
            "blur_value":      blur_value,
            "weight_mode":     weight_mode,
        },
        "ocr": {
            "raw_score":             ocr_score,
            "weight":                weights["ocr"],
            "weighted":              round(ocr_score * weights["ocr"], 4),
            "nafdac_number":         nafdac_number,
            "brand_detected":        ocr_signal.get("brand_detected"),
            "structural_score":      ocr_signal.get("structural_score"),
            "lookalike_corrections": ocr_signal.get("lookalike_corrections", []),
        },
        "reg": {
            "raw_score":                  reg_score,
            "weight":                     weights["reg"],
            "weighted":                   round(reg_score * weights["reg"], 4),
            "status_code":                reg_signal.get("status_code"),
            "retrieval_path":             retrieval_path,
            "retrieval_confidence":       reg_signal.get("retrieval_confidence"),
            "fallback_used":              fallback_used,
            "tools_called":               reg_signal.get("tools_called", []),
            "nafdac_registered_product":  reg_signal.get("nafdac_registered_product"),
            "nafdac_registered_category": reg_signal.get("nafdac_registered_category"),
            "expiry_date_iso":            reg_signal.get("expiry_date_iso"),
            "days_remaining":             reg_signal.get("days_remaining"),
            "is_near_expiry":             reg_signal.get("is_near_expiry", False),
        },
    }

    # Build warnings 
    warnings = _build_warnings(
        visual_signal     = visual_signal,
        ocr_signal     = ocr_signal,
        reg_signal     = reg_signal,
        weight_mode   = weight_mode,
        damage_score  = damage_score,
        blur_value    = blur_value,
        fallback_used = fallback_used,
    )

    # Assemble and return 
    return {
        # Core verdict 
        "verdict":          verdict,
        "final_score":      round(final_score, 4),
        "severity":         severity,
        "confidence_label": confidence_label,
        "rescan_required":  False,

        # Weight audit
        "weight_mode":    weight_mode,
        "weights_used":   weights,
        "retrieval_path": retrieval_path,

        # Overrides
        "override_applied": applied_override is not None,
        "applied_override": applied_override,
        "all_overrides":    overrides_triggered,

        # Breakdown 
        "breakdown": breakdown,
        "warnings":  warnings,

        #  N-ATLAS feed 
        "atlas_detail":  reg_signal.get("atlas_detail", ""),
        "atlas_summary": reg_signal.get("summary",      ""),

        #  Evidence fields (forwarded to decision_classifier -> evidence_packager) 
        "evidence": {
            "nafdac_number":             nafdac_number,
            "ocr_product_name":          ocr_product_name,
            "brand_detected":            ocr_signal.get("brand_detected"),
            "brand_anomaly_flag":        ocr_signal.get("brand_anomaly_flag"),
            "lookalike_corrections":     ocr_signal.get("lookalike_corrections", []),
            "product_matched_visual":    visual_signal.get("product_matched"),
            "nafdac_registered_product": reg_signal.get("nafdac_registered_product"),
            "name_identity_check":       name_id_check,
            "damage_score":              damage_score,
            "blur_value":                blur_value,
            "weight_mode":               weight_mode,
            "missing_fields":            ocr_signal.get("missing_fields", []),
            "reg_status_code":            reg_signal.get("status_code"),
            "reg_severity":               reg_signal.get("severity"),
            "matched_record":            reg_signal.get("matched_record"),
            "retrieval_path":            retrieval_path,
            "fallback_used":             fallback_used,
            "tools_called":              reg_signal.get("tools_called", []),
            "reasoning_trace":           reg_signal.get("reasoning_trace", []),
            # Image retraining pipeline
            "save_for_retraining": weight_mode == "DAMAGED",
            "save_reason":         _save_reason(damage_score, blur_value),
        },

        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


#  Private helpers 

def _resolve_weights(damage_score: float, fallback_used: bool) -> tuple:
    """
    Select the correct weight set based on scan quality and Regulatory retrieval path.

    Priority order:
      1. DAMAGED  - damage_score >= DAMAGED_SCORE_FLOOR
         Visual is blur-compromised. DAMAGED always overrides FALLBACK.
      2. FALLBACK - damage_score < DAMAGED_SCORE_FLOOR AND fallback_used=True
         Regulatory used semantic search. Visual and OCR lead.
      3. BASE     - clean scan, exact NAFDAC lookup.
         Full confidence in all three signals.

    Returns:
        (weights dict, mode label string)
        Mode label is stored in breakdown and evidence for audit trail.
    """
    if damage_score >= DAMAGED_SCORE_FLOOR:
        return SIGNAL_WEIGHTS_DAMAGED,  "DAMAGED"
    if fallback_used:
        return SIGNAL_WEIGHTS_FALLBACK, "FALLBACK"
    return SIGNAL_WEIGHTS,             "BASE"


def _compute_weighted(visual: float, ocr: float, reg: float, weights: dict) -> float:
    """
    Apply the weighted fusion formula. All inputs and output are 0.0-1.0.
    """
    return round(
        (visual * weights["visual"]) +
        (ocr * weights["ocr"])    +
        (reg * weights["reg"]),
        4,
    )


def _build_warnings(
    visual_signal:    dict,
    ocr_signal:    dict,
    reg_signal:    dict,
    weight_mode:  str,
    damage_score: float,
    blur_value:   float,
    fallback_used:bool,
) -> list:
    """
    Build the warnings list forwarded to ScanResult.
    Each warning has a 'type' key and a 'message' key.
    Warnings are informational - they do not change the verdict.
    """
    warnings = []

    # Low scan quality - image was blurry but recoverable
    if weight_mode == "DAMAGED":
        warnings.append({
            "type": "LOW_SCAN_QUALITY",
            "message": (
                f"Image blur detected (blur_value={blur_value:.1f}, "
                f"damage_score={damage_score}). "
                f"Visual weight reduced to {SIGNAL_WEIGHTS_DAMAGED['visual']}. "
                f"Regulatory regulatory signal is carrying this scan "
                f"(weight={SIGNAL_WEIGHTS_DAMAGED['reg']}). "
                f"Rescan in better lighting for a higher-confidence result."
            ),
        })

    # Regulatory semantic fallback - agent could not find exact NAFDAC match
    if fallback_used:
        warnings.append({
            "type": "SEMANTIC_FALLBACK_USED",
            "message": (
                f"Regulatory ReAct agent could not find an exact NAFDAC number match. "
                f"Used semantic text search instead "
                f"(retrieval_confidence={reg_signal.get('retrieval_confidence', 0.70):.2f}). "
                f"Regulatory weight reduced to {SIGNAL_WEIGHTS_FALLBACK['reg']}. "
                f"Visual and OCR are leading this scan."
            ),
        })

    # Near expiry - product registration will expire soon
    if reg_signal.get("is_near_expiry"):
        days = reg_signal.get("days_remaining", "unknown")
        warnings.append({
            "type": "NEAR_EXPIRY",
            "message": (
                f"Product registration expires in {days} day(s). "
                f"The product is currently valid but verify with the vendor. "
                + reg_signal.get("detail", "")
            ),
        })

    # Lookalike character substitutions - classic counterfeit label technique
    if ocr_signal.get("lookalike_corrections"):
        warnings.append({
            "type": "LOOKALIKE_CHARS_DETECTED",
            "message": (
                f"Suspicious character substitutions detected on label: "
                f"{ocr_signal['lookalike_corrections']}. "
                f"This is a classic counterfeiting technique - "
                f"e.g. digit '0' replacing letter 'o', '1' replacing 'l'."
            ),
        })

    # Soft regulatory warnings (DB gap, subcategory mismatch, etc.)
    if reg_signal.get("soft_warning"):
        warnings.append({
            "type":    reg_signal.get("status_code", "REG_WARNING"),
            "message": reg_signal["soft_warning"],
        })

    return warnings


def _save_reason(damage_score: float, blur_value: float) -> str | None:
    """
    Return a save reason string if this image should be saved for model retraining.
    Returns None for clean scans - they are saved through the normal evidence flow.
    """
    if damage_score >= 0.8 and blur_value < EXTREME_BLUR_CEILING:
        return "UNUSABLE_EXTREME_BLUR"
    if damage_score >= 0.8:
        return "LOW_SCAN_QUALITY_HEAVY"
    if damage_score >= DAMAGED_SCORE_FLOOR:
        return "LOW_SCAN_QUALITY_MODERATE"
    return None


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def _name_match(registered: str, candidate: str) -> dict:
    """
    Fuzzy product-name comparison. Returns {is_match, similarity, method, ...}.

    Three-stage check (in priority order):
      1. Exact match after normalization          — handles case/punctuation noise
      2. Substring containment (no-space forms)  — handles "CloseUp" vs "Close Up Toothpaste"
                                                   and "Coco Pops" vs "KELLOGG'S COCO POPS"
      3. SequenceMatcher ratio on no-space forms — handles minor OCR character noise
         "Cocoa Pups" vs "Coco Pops" scores ~0.82 → below NAME_MATCH_THRESHOLD (0.85) → MISMATCH
    """
    reg_norm  = _normalize_name(registered)
    cand_norm = _normalize_name(candidate)

    if reg_norm == cand_norm:
        return {"is_match": True, "similarity": 1.0, "method": "exact",
                "registered_norm": reg_norm, "candidate_norm": cand_norm}

    reg_ns  = reg_norm.replace(" ", "")
    cand_ns = cand_norm.replace(" ", "")
    if cand_ns in reg_ns or reg_ns in cand_ns:
        return {"is_match": True, "similarity": 0.95, "method": "substring",
                "registered_norm": reg_norm, "candidate_norm": cand_norm}

    char_sim = round(difflib.SequenceMatcher(None, reg_ns, cand_ns).ratio(), 4)
    return {
        "is_match":        char_sim >= NAME_MATCH_THRESHOLD,
        "similarity":      char_sim,
        "method":          "char_similarity",
        "registered_norm": reg_norm,
        "candidate_norm":  cand_norm,
    }


def _check_name_identity(
    reg_signal:             dict,
    ocr_product_name:       "str | None",
    visual_product_matched: "str | None",
) -> dict:
    """
    Cross-validate product identity when the NAFDAC number is VERIFIED.

    Catches the primary counterfeit vector: a genuine NAFDAC number affixed to
    packaging that carries a different product name (e.g. "Cocoa Pups" on a
    package using the NAFDAC number registered to "Coco Pops").

    Checks performed (each only when the relevant name is available):
      (a) Registered name  vs  OCR-extracted product name from the label
      (b) Visual-matched product name  vs  OCR-extracted product name
          (image LOOKS LIKE X but label text says Y → strong counterfeit signal)

    Returns a result dict that is forwarded into evidence and the override hierarchy.
    Logs the comparison at WARNING level when a mismatch is detected.
    """
    result: dict = {
        "mismatch_detected": False,
        "registered_name":   None,
        "ocr_check":         None,
        "visual_check":      None,
        "reason":            None,
    }

    status_code = reg_signal.get("status_code", "")
    if status_code not in ("VERIFIED", "VERIFIED_NEAR_EXPIRY"):
        return result

    # When the regulatory agent fell back to semantic search the matched product
    # is a nearest-neighbour guess, not a confirmed identity.  Comparing a guessed
    # registered name against the label name would produce false IDENTITY_MISMATCH
    # verdicts (e.g. AXE deodorant flagged because semantic search matched Vaseline).
    if reg_signal.get("fallback_used"):
        return result

    registered_name = reg_signal.get("nafdac_registered_product")
    if not registered_name:
        return result

    result["registered_name"] = registered_name

    # Ignore visual sentinel values
    if visual_product_matched in (None, "UNKNOWN", "NO_PRODUCT_DETECTED", ""):
        visual_product_matched = None

    if not ocr_product_name and not visual_product_matched:
        return result

    mismatch_parts = []

    # Check (a): registered name vs OCR product name extracted from the label
    if ocr_product_name:
        ocr_res = _name_match(registered_name, ocr_product_name)
        result["ocr_check"] = {
            "performed":       True,
            "is_match":        ocr_res["is_match"],
            "similarity":      ocr_res["similarity"],
            "method":          ocr_res["method"],
            "registered_norm": ocr_res["registered_norm"],
            "candidate_norm":  ocr_res["candidate_norm"],
        }
        if not ocr_res["is_match"]:
            mismatch_parts.append(
                f"OCR label name '{ocr_product_name}' "
                f"(similarity={ocr_res['similarity']:.2f}) does not match "
                f"registered name '{registered_name}'"
            )

    # Check (b): visual-matched product vs OCR product name on the label.
    # If the image LOOKS LIKE product X but the label text says Y (and X≠Y) that is
    # a direct counterfeit indicator even when check (a) could not be performed.
    if visual_product_matched and ocr_product_name:
        vis_res = _name_match(visual_product_matched, ocr_product_name)
        result["visual_check"] = {
            "performed":       True,
            "is_match":        vis_res["is_match"],
            "similarity":      vis_res["similarity"],
            "method":          vis_res["method"],
            "registered_norm": vis_res["registered_norm"],
            "candidate_norm":  vis_res["candidate_norm"],
        }
        if not vis_res["is_match"]:
            mismatch_parts.append(
                f"Visual identity '{visual_product_matched}' "
                f"(similarity={vis_res['similarity']:.2f}) does not match "
                f"label text '{ocr_product_name}'"
            )
    elif visual_product_matched:
        # OCR name unavailable — fall back to registered vs visual match
        vis_res = _name_match(registered_name, visual_product_matched)
        result["visual_check"] = {
            "performed":       True,
            "is_match":        vis_res["is_match"],
            "similarity":      vis_res["similarity"],
            "method":          vis_res["method"],
            "registered_norm": vis_res["registered_norm"],
            "candidate_norm":  vis_res["candidate_norm"],
        }
        if not vis_res["is_match"]:
            mismatch_parts.append(
                f"Visual identity '{visual_product_matched}' "
                f"(similarity={vis_res['similarity']:.2f}) does not match "
                f"registered name '{registered_name}'"
            )

    if mismatch_parts:
        result["mismatch_detected"] = True
        result["reason"] = (
            f"NAFDAC number is registered for '{registered_name}' but "
            + "; ".join(mismatch_parts) + ". "
            "Real NAFDAC number on mismatched packaging is a confirmed counterfeit pattern."
        )
        logger.warning(
            "NAME_IDENTITY_MISMATCH | nafdac_registered=%r | ocr_name=%r | "
            "visual_matched=%r | %s",
            registered_name, ocr_product_name, visual_product_matched,
            "; ".join(mismatch_parts),
        )
    else:
        logger.info(
            "NAME_IDENTITY_CHECK passed | nafdac_registered=%r | ocr_name=%r | "
            "visual_matched=%r",
            registered_name, ocr_product_name, visual_product_matched,
        )

    return result


def _build_rescan_required(
    blur_value:   float,
    damage_score: float,
    visual_signal:    dict,
    ocr_signal:    dict,
) -> dict:
    """
    Return a RESCAN_REQUIRED result when the image is too degraded to score.

    This is NOT a FAKE verdict - the product has not been assessed.
    The image is flagged for saving to improve the Visual DamageDetector model.
    No NAFDAC report is generated.
    """
    reason = (
        f"Image is too blurry to scan reliably "
        f"(blur_value={blur_value:.1f}, threshold={EXTREME_BLUR_CEILING}). "
        f"Please hold your phone steady in good lighting and try again."
    )
    return {
        "verdict":          "RESCAN_REQUIRED",
        "final_score":      None,
        "severity":         "NONE",
        "confidence_label": "NONE",
        "rescan_required":  True,
        "rescan_reason":    reason,

        "weight_mode":    "REJECTED",
        "weights_used":   None,
        "retrieval_path": None,

        "override_applied": False,
        "applied_override": None,
        "all_overrides":    [],

        "breakdown": {},
        "warnings": [{
            "type":    "RESCAN_REQUIRED",
            "message": reason,
        }],

        "atlas_detail":  "",
        "atlas_summary": "",

        # Evidence - image saved for retraining, no NAFDAC report
        "evidence": {
            "nafdac_number":          ocr_signal.get("nafdac_number"),
            "damage_score":           damage_score,
            "blur_value":             blur_value,
            "weight_mode":            "REJECTED",
            "save_for_retraining":    True,
            "save_reason":            "UNUSABLE_EXTREME_BLUR",
            "product_matched_visual": visual_signal.get("product_matched"),
        },

        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
