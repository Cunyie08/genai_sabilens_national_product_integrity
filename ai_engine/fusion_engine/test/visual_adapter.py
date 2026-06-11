# Normalizes Visual output -> FusionSignal  (v2 — EfficientNet dual-head)

"""
visual_adapter.py  —  SabiLens Fusion Engine
=============================================
WHAT CHANGED FROM v1 AND WHY
------------------------------
v1 consumed only 6 fields from VisualPipeline:
    product, Visual Similarity, damage_score, blur_value, confidence, verdict

v2 VisualPipeline now outputs 11 fields including forensic signals that
v1 never forwarded to Fusion:
    margin          : gap to 2nd-best product match (ambiguity detector)
    anomaly_flag    : True when similarity < 0.67 (below forensic threshold)
    ambiguity_flag  : True when margin < 0.08 (match too close to another product)
    penalty_applied : actual penalty multiplier used (1.0 = no penalty)
    flags           : human-readable list of active warnings from v2 pipeline

These are now extracted and forwarded so:
  1. fusion_engine.run_fusion() receives them in the visual_signal dict
  2. breakdown["visual"] includes them for audit trail
  3. The override logic uses anomaly_flag as an additional override trigger
     (not just raw_similarity < 0.20 as in v1)

OVERRIDE CHANGES:
  v1: override fires if raw_similarity < 0.20  (almost never fires — too permissive)
  v2: override fires if:
      - raw_similarity < LOGO_MATCH_FLOOR_THRESHOLD (0.20)  [v1 rule, kept]
      - anomaly_flag=True AND penalty_applied < 0.6         [new v2 rule]
        This catches fakes that scored 0.61-0.67 similarity (above old threshold
        but still below the forensic anomaly band). These were the exact fakes
        that slipped through in testing.

REMOVED:
  - Unused import: `from ai_engine.visual.vision_engine import similarity`
    This caused an ImportError and was never referenced anywhere in the file.

BACKWARD COMPATIBILITY:
  All v1 fields still present in output dict.
  New v2 fields default safely (False / 1.0 / []) if absent from visual_output,
  so old Visual outputs still pass through without crashing.
"""

from datetime import datetime, timezone
from ai_engine.fusion_engine.config.thresholds import LOGO_MATCH_FLOOR_THRESHOLD


def adapt(visual_output: dict) -> dict:
    """
    Normalise VisualPipeline v2 output into a standard Fusion engine signal.

    Args:
        visual_output: Raw dict from VisualPipeline.analyze()

    Returns:
        FusionSignal dict with all fields fusion_engine.run_fusion() needs.
    """
    # Non-product image
    if visual_output.get("no_product_detected"):
        return {
            "source":              "visual",
            "fusion_score":        0.0,
            "raw_confidence":      0.0,
            "raw_similarity":      min(float(visual_output.get("Visual Similarity", 0.0)), 1.0),
            "damage_score":        float(visual_output.get("damage_score", 0.1)),
            "blur_value":          float(visual_output.get("blur_value", 60.0)),
            "product_matched":     "NO_PRODUCT_DETECTED",
            "Visual_verdict":      "Fake",
            # v2 fields
            "margin":              0.0,
            "anomaly_flag":        True,
            "ambiguity_flag":      True,
            "penalty_applied":     1.0,
            "visual_flags":        ["NO_PRODUCT_DETECTED"],
            # override
            "override_flag":       True,
            "override_reason":     "NO_PRODUCT_DETECTED",
            "no_product_detected": True,
            "timestamp":           datetime.now(timezone.utc).isoformat(),
        }

    # ── Extract v1 fields ─────────────────────────────────────────────────
    confidence      = min(float(visual_output.get("confidence",        0.0)), 1.0)
    raw_similarity  = min(float(visual_output.get("Visual Similarity", 0.0)), 1.0)
    damage_score    = float(visual_output.get("damage_score", 0.1))
    blur_value      = float(visual_output.get("blur_value",   60.0))
    product_matched = visual_output.get("product",  "UNKNOWN")
    visual_verdict  = visual_output.get("verdict",  "Fake")

    # ── Extract v2 fields (safe defaults for backward compat) ─────────────
    margin          = float(visual_output.get("margin",          0.0))
    anomaly_flag    = bool(visual_output.get("anomaly_flag",     False))
    ambiguity_flag  = bool(visual_output.get("ambiguity_flag",   False))
    penalty_applied = float(visual_output.get("penalty_applied", 1.0))
    visual_flags    = list(visual_output.get("flags",            []))

    # Fusion score: confidence is already penalty-adjusted by v2 pipeline
    fusion_score = round(confidence, 4)

    # ── Override logic (v2 expanded) ──────────────────────────────────────
    override_flag   = False
    override_reason = None

    # Rule 1 (v1): critically low raw similarity
    if raw_similarity < LOGO_MATCH_FLOOR_THRESHOLD:
        override_flag   = True
        override_reason = (
            f"Visual: raw logo similarity ({raw_similarity:.3f}) is below the "
            f"{LOGO_MATCH_FLOOR_THRESHOLD} minimum threshold. "
            f"Product fails minimum visual match — verdict floored to SUSPICIOUS."
        )

    # Rule 2 (v2 NEW): anomaly flag active AND heavy penalty applied
    # penalty_applied < 0.5 means BOTH blur anomaly AND similarity anomaly fired
    # This is a strong fake signal — floor to FAKE, not just SUSPICIOUS
    elif anomaly_flag and penalty_applied < 0.5:
        override_flag   = True
        override_reason = (
            f"Visual v2: anomaly_flag=True with penalty_applied={penalty_applied:.2f} "
            f"(multiple penalties active). Similarity={raw_similarity:.3f}, "
            f"confidence={confidence:.3f}. Strong fake signal — verdict forced to FAKE."
        )

    # Rule 3 (v2): anomaly flag only (single penalty) — floor to SUSPICIOUS
    elif anomaly_flag and penalty_applied < 0.6:
        override_flag   = True
        override_reason = (
            f"Visual v2: anomaly_flag=True with penalty_applied={penalty_applied:.2f}. "
            f"Similarity ({raw_similarity:.3f}) in forensic anomaly band. "
            f"Confidence={confidence:.3f} — verdict floored to SUSPICIOUS."
        )

    return {
        # ── v1 fields (unchanged) ─────────────────────────────────────────
        "source":          "VISUAL",
        "fusion_score":    fusion_score,
        "raw_confidence":  round(confidence,     4),
        "raw_similarity":  round(raw_similarity, 4),
        "damage_score":    round(damage_score,   4),
        "blur_value":      round(blur_value,     4),
        "product_matched": product_matched,
        "Visual_verdict":  visual_verdict,
        "override_flag":   override_flag,
        "override_reason": override_reason,
        # ── v2 fields (new) ───────────────────────────────────────────────
        "margin":          round(margin, 4),
        "anomaly_flag":    anomaly_flag,
        "ambiguity_flag":  ambiguity_flag,
        "penalty_applied": round(penalty_applied, 4),
        "visual_flags":    visual_flags,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


def validate(visual_output: dict) -> list[str]:
    """
    Check that Visual output has all required fields before adaptation.
    Returns a list of missing/invalid field names (empty = valid).
    """
    if visual_output.get("no_product_detected"):
        return []

    texts = []
    required = ["confidence", "Visual Similarity", "damage_score", "product", "verdict"]

    for field in required:
        if field not in visual_output:
            texts.append(f"Missing field: '{field}'")

    if "blur_value" not in visual_output:
        texts.append(
            "WARNING: 'blur_value' missing from Visual output. "
            "Defaulting to 60.0 (sharp) — RESCAN_REQUIRED logic will not fire correctly."
        )

    confidence = visual_output.get("confidence", -1)
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.001):
        texts.append(f"'confidence' must be float in [0.0, 1.0], got: {confidence!r}")

    similarity = visual_output.get("Visual Similarity", -1)
    if not isinstance(similarity, (int, float)) or not (0.0 <= float(similarity) <= 1.001):
        texts.append(f"'Visual Similarity' must be float in [0.0, 1.0], got: {similarity!r}")

    verdict = visual_output.get("verdict", "")
    if verdict not in {"Authentic", "Suspicious", "Fake"}:
        texts.append(
            f"'verdict' must be 'Authentic', 'Suspicious', or 'Fake' (Title case), "
            f"got: {verdict!r}"
        )

    return texts