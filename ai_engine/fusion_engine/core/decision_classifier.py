"""
This file contains Fusion Engine's Decision Classifier

Maps a FusionResult to a final user-facing verdict, action,
instruction, and NAFDAC report priority.

POSITION IN PIPELINE:
  fusion_engine.run_fusion()  ->  classify()  ->  evidence_packager.package()

ESPONSIBILITIES:
  1. Translate verdict -> user action     (BUY / CAUTION / DO NOT BUY)
  2. Assign NAFDAC report priority       (AUTO / PROMPT / NONE)
  3. Generate context-aware instruction  (full, for N-ATLAS translation)
  4. Generate simple instruction         (short, voice-first, for Mama Bola)
  5. Inject warnings into atlas_instruction
  6. Generate a deterministic scan_id    (hex digest, traceable in DB)
  7. Build override_summary              (human-readable override audit string)

ACTION MAP:
  AUTHENTIC   ->  BUY          - product passed all checks
  SUSPICIOUS  ->  CAUTION      - proceed carefully, seek second opinion
  FAKE        ->  DO NOT BUY   - do not purchase, report immediately

REPORT PRIORITY:
  FAKE        ->  AUTO    - evidence logged automatically, no user action
  SUSPICIOUS  ->  PROMPT  - user asked if they want to file a report
  AUTHENTIC   ->  NONE    - no report needed

RESCAN_REQUIRED HANDLING:
  If fusion_result["verdict"] == "RESCAN_REQUIRED", classify() returns
  a minimal result with action="RESCAN" and report_priority="NONE".
  No instruction is built, no scan_id is generated from evidence.
  This state is passed through to main.py which surfaces it to the API.

SCALABILITY NOTES:
  - Add new verdicts to _ACTION_MAP, _REPORT_PRIORITY, _INSTRUCTIONS,
    and _SIMPLE_INSTRUCTIONS together - they must always be in sync.
  - Add new warning injection types in _inject_warnings().
  - Add new instruction enrichment cases in _build_instruction().
  - Do not import from fusion_engine.py - this file is downstream only.
  - scan_id uses SHA-256 (not MD5) for collision resistance at scale.
    Format: first 12 hex chars of digest, uppercase, e.g. "A3F2B1C4D5E6"
"""

 
import uuid
from datetime import datetime, timezone
import json
import uuid
from datetime import datetime, timezone


# Action instruction map
_ACTION_MAP = {
    "AUTHENTIC":        "BUY",
    "SUSPICIOUS":       "CAUTION",
    "FAKE":             "DO NOT BUY",
    "RESCAN_REQUIRED":  "RESCAN",
    "NOT_VERIFIED":    "VERIFY", 
}

# NAFDAC report priority map 
_REPORT_PRIORITY = {
    "AUTHENTIC":        "NONE",
    "SUSPICIOUS":       "PROMPT",
    "FAKE":             "AUTO",
    "RESCAN_REQUIRED":  "NONE",      # No report for rejected scans, image saved for retraining
    "NOT_VERIFIED":    "NONE",       # Not confirmed fake; no report filed
}

# User-facing instruction templates 
# Full instruction templates (N-ATLAS for Yoruba/Hausa/Igbo/Pidgin) 
_INSTRUCTIONS = {
    "AUTHENTIC": (
        "This product has passed all verification checks."
        "The NAFDAC number is valid, the brand is authentic,"
        "and the product category matches its registration."
        "It is safe to purchase."
    ),
    "SUSPICIOUS": (
        "This product raised concerns during verification."
        "We could not fully confirm its authenticity."
        "Proceed with caution. If possible, purchase from a"
        "different vendor or verify with NAFDAC directly."
    ),
    "FAKE": (
        "WARNING: This product has FAILED verification."
        "It shows strong signs of being counterfeit."
        "Do NOT purchase this product."
        "Your scan has been logged and reported to NAFDAC."
    ),
    "RESCAN_REQUIRED": (
        "We could not scan this product clearly."
        "Please hold your phone steady in good lighting and try again."
    ),
    "NOT_VERIFIED": (                     
        "This product could not be verified in the SabiLens database."
        "This does not mean it is fake; our database is still growing."
        "and may not yet cover all registered NAFDAC products."
        "Check the NAFDAC number directly at www.nafdac.gov.ng before purchasing."
    )
}


# Simple instructions (voice-first, non-literate users , Mama Ola)
# Maximum two sentences. No technical language. Direct action.
_SIMPLE_INSTRUCTIONS = {
    "AUTHENTIC":        "This product is real. You can buy it.",
    "SUSPICIOUS":       "We are not sure about this product. Be careful.",
    "FAKE":             "Do not buy this product. It is fake. We have reported it.",
    "RESCAN_REQUIRED":  "We could not read this product clearly. Please try scanning again.",
    "NOT_VERIFIED":    "We could not find this product in our database. Check with NAFDAC before buying.",
}

#  Warning type: atlas instruction appendage 
# Injected into atlas_instruction after the base instruction is built.
_WARNING_APPENDAGES = {
    "NEAR_EXPIRY": (
        "Note: This product's registration is expiring soon. "
        "Verify with the vendor before purchasing."
    ),
    "LOOKALIKE_CHARS_DETECTED": (
        " Warning: Suspicious character substitutions were detected "
        "on the label. This may indicate tampering."
    ),
    "LOW_SCAN_QUALITY": (
        " Note: Scan quality was low. Result confidence is reduced. "
        "Rescan in better lighting if possible."
    ),
    "SEMANTIC_FALLBACK_USED": (
        " Note: The NAFDAC number could not be matched exactly. "
        "A partial match was used. Verify independently if in doubt."
    ),
    "NAME_IDENTITY_MISMATCH": (
        " Warning: The NAFDAC number on this product belongs to a different product. "
        "A genuine registration number on mismatched packaging is a known counterfeit technique."
    ),
}

# Main classify function
def classify(fusion_result: dict) -> dict:
    """
    Maps a fusion engine result to a final user-facing decision.

    Args:
        fusion_result: Output dict from core/fusion_engine.run_fusion()

    Returns:
        ClassificationResult dict consumed by evidence_packager.package()
        and returned to the API layer via main.py run_scan().
    """


    verdict         = fusion_result.get("verdict", "FAKE")
    final_score     = fusion_result.get("final_score", 0.0)
    severity        = fusion_result.get("severity", "CRITICAL")
    confidence_label = fusion_result.get("confidence_label", "VERY LOW")
    override_applied = fusion_result.get("override_applied", False)
    applied_override = fusion_result.get("applied_override")
    warnings        = fusion_result.get("warnings", [])
    evidence        = fusion_result.get("evidence", {})
    breakdown       = fusion_result.get("breakdown", {})

    # Product not in SabiLens DB is a coverage gap, not a confirmed counterfeit.
    # Intercept BEFORE action/priority/instruction are built so the corrected
    # verdict flows through all four maps automatically.
    #
    # Rules:
    #   visual < 0.60 AND ocr < 0.60   :  both signals weak + not in DB
    #                                  :  genuinely unknown, NOT_VERIFIED
    #   visual >= 0.60                 :  product looks authentic visually
    #                                  :  downgrade FAKE to SUSPICIOUS
    #   strong counterfeit signals     :  FAKE preserved (reg_status not NOT_FOUND)

    reg_status   = evidence.get("reg_status_code", "")
    visual_score = breakdown.get("visual", {}).get("raw_score", 0.0)
    ocr_score    = breakdown.get("ocr",    {}).get("raw_score", 0.0)

    if reg_status == "NOT_FOUND" and verdict in ("FAKE", "SUSPICIOUS"):
        if visual_score < 0.60 and ocr_score < 0.60:
            # Both signals weak + not in DB = genuinely unknown
            verdict = "NOT_VERIFIED"
        elif verdict == "FAKE":
            # Visual looks reasonable but reg missing — downgrade to SUSPICIOUS
            verdict = "SUSPICIOUS"

    # Core classification
    action           = _ACTION_MAP.get(verdict, "DO NOT BUY THIS PRODUCT. IT IS A COUNTERFEIT.")
    report_priority  = _REPORT_PRIORITY.get(verdict, "AUTO")
    instruction      = _build_instruction(verdict, fusion_result)
    simple_instruction = _SIMPLE_INSTRUCTIONS.get(verdict, _SIMPLE_INSTRUCTIONS["FAKE"])

    # Context-aware simple_instruction overrides for known fake patterns
    if verdict == "FAKE" and (applied_override or {}).get("type") == "IDENTITY_MISMATCH":
        name_id         = evidence.get("name_identity_check", {})
        registered_name = (
            name_id.get("registered_name") or
            evidence.get("nafdac_registered_product") or
            "the genuine product"
        )
        # Prefer the front-panel label (what the fake packaging actually says);
        # fall back to the single-image extracted name for backward compatibility.
        front_label = (
            name_id.get("front_label") or
            evidence.get("front_panel_name") or
            evidence.get("ocr_product_name") or
            ""
        )
        if front_label:
            simple_instruction = (
                f"The NAFDAC number on this product is registered to '{registered_name}', "
                f"but the front of this pack reads '{front_label}'. "
                "This is a fake product. Do not buy it."
            )
        else:
            simple_instruction = (
                f"This product's NAFDAC number is registered to '{registered_name}', "
                "but this is not that product. Do not buy it."
            )

    elif verdict == "FAKE" and reg_status == "SUBCATEGORY_MISMATCH":
        nafdac = evidence.get("nafdac_number", "") or ""
        registered_cat = (
            breakdown.get("reg", {}).get("nafdac_registered_category") or
            "a different category"
        )
        simple_instruction = (
            f"The NAFDAC number on this product ({nafdac}) is registered "
            f"for a '{registered_cat}' product — not what you are holding. "
            f"This is a classic counterfeit pattern."
        )

    atlas_instruction  = _inject_warnings(instruction, warnings)

    # Override summary for transparency 
    override_summary = None
    if override_applied and applied_override:
        override_summary = (
            f"[{applied_override['source']}: {applied_override['type']}] "
            f"{applied_override['reason']}"
        )

    # Generate deterministic scan_id 
    # SHA-256 over verdict + score + nafdac + UTC timestamp.
    # Deterministic within a single run; unique across runs due to timestamp.
    scan_id = str(uuid.uuid4())


    return {
        "action":             action,
        "verdict":            verdict,
        "final_score":        final_score,
        "severity":           severity,
        "confidence_label":   confidence_label,
        "report_priority":    report_priority,
        "instruction":        instruction,
        "simple_instruction": simple_instruction,
        "atlas_instruction":  atlas_instruction,
        "override_applied":   override_applied,
        "override_summary":   override_summary,
        "warnings":           warnings,
        "evidence":           evidence,
        "breakdown":          breakdown,
        "scan_id":            scan_id,
        "timestamp":          datetime.now(timezone.utc).isoformat(),
    }




def _build_instruction(verdict: str, fusion_result: dict) -> str:
    """
    Build a context-aware instruction string for N-ATLAS.

    Starts from the base template for the verdict and enriches it with
    product-specific details extracted from the fusion result evidence.
    The enriched string is what gets translated into Yoruba/Hausa/Igbo/Pidgin.

    Args:
        verdict:        The fusion verdict string.
        fusion_result:  Full FusionResult dict from fusion_engine.run_fusion().

    Returns:
        Enriched instruction string. Always returns a non-empty string.
    """
    base = _INSTRUCTIONS.get(verdict, _INSTRUCTIONS["FAKE"])
    evidence = fusion_result.get("evidence", {})
    breakdown = fusion_result.get("breakdown", {})

    # Prefer the DB-registered name; fall back to visual match; fall back to generic
    product_name = (
        evidence.get("nafdac_registered_product") or
        evidence.get("product_matched_visual")    or
        "this product"
    )
    nafdac     = evidence.get("nafdac_number",   "") or ""
    reg_status = evidence.get("reg_status_code", "") or ""

    if verdict == "FAKE":
        applied_override_info = fusion_result.get("applied_override") or {}
        if applied_override_info.get("type") == "IDENTITY_MISMATCH":
            name_id         = evidence.get("name_identity_check", {})
            registered_name = (
                name_id.get("registered_name") or
                evidence.get("nafdac_registered_product") or
                "the genuine product"
            )
            front_label = (
                name_id.get("front_label") or
                evidence.get("front_panel_name") or
                evidence.get("ocr_product_name") or
                ""
            )
            nafdac     = evidence.get("nafdac_number", "") or ""
            nafdac_str = f" ({nafdac})" if nafdac else ""
            label_str  = f" '{front_label}'" if front_label else " a different product name"
            base = (
                f"WARNING: This product has FAILED verification. "
                f"The NAFDAC number{nafdac_str} is registered for '{registered_name}', "
                f"but the front of this packaging shows{label_str}. "
                "A genuine NAFDAC number on packaging that does not match the registered product "
                "is a confirmed counterfeit technique. "
                "Do NOT purchase this product. "
                "Your scan has been logged and reported to NAFDAC."
            )
            return base

        if reg_status == "SUBCATEGORY_MISMATCH":
            registered_cat = (
                breakdown.get("reg", {}).get("nafdac_registered_category") or
                "a different category"
            )
            base += (
                f" The NAFDAC number on this product ({nafdac}) is registered "
                f"for a '{registered_cat}' product — not what you are holding. "
                f"This is a classic counterfeit pattern."
            )
        elif reg_status == "EXPIRED":
            base += (
                f" The registration for '{product_name}' has expired. "
                f"This product is no longer authorised for sale in Nigeria."
            )
        elif reg_status == "AGENT_ERROR":
            base += (
                " The NAFDAC verification system could not be reached. "
                "Authenticity cannot be confirmed. Do not purchase this product."
            )

    elif verdict == "AUTHENTIC":
        base += f" Confirmed product: {product_name}."

    elif verdict == "SUSPICIOUS":
        if not evidence.get("nafdac_number"):
            base += (
                " The NAFDAC number could not be read from this label. "
                "A genuine product always has a visible, scannable NAFDAC number."
            )

    elif verdict == "NOT_VERIFIED":
        nafdac_str = f" ({nafdac})" if nafdac else ""
        base += (
            f" The NAFDAC number{nafdac_str} was not found in the SabiLens "
            f"verified product registry. As our database grows, this product "
            f"may be added. For now, verify at www.nafdac.gov.ng."
        )

    return base


def _inject_warnings(instruction: str, warnings: list) -> str:
    """
    Append warning appendages to the atlas_instruction string.
    Each warning type in _WARNING_APPENDAGES is appended once if present.
    Preserves insertion order — most critical warnings appear first.

    Args:
        instruction: Base instruction string from _build_instruction().
        warnings:    List of warning dicts from fusion_engine.run_fusion().

    Returns:
        Enriched atlas_instruction string.
    """
    seen_types = set()
    result     = instruction

    for warning in warnings:
        w_type = warning.get("type", "")
        if w_type in _WARNING_APPENDAGES and w_type not in seen_types:
            result += _WARNING_APPENDAGES[w_type]
            seen_types.add(w_type)

    return result



