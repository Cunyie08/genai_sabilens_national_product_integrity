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
}

# NAFDAC report priority map 
_REPORT_PRIORITY = {
    "AUTHENTIC":        "NONE",
    "SUSPICIOUS":       "PROMPT",
    "FAKE":             "AUTO",
    "RESCAN_REQUIRED":  "NONE",    # No report for rejected scans - image saved for retraining
}

# User-facing instruction templates 
# Full instruction templates (N-ATLAS for Yoruba/Hausa/Igbo/Pidgin) 
_INSTRUCTIONS = {
    "AUTHENTIC": (
        "This product has passed all verification checks. "
        "The NAFDAC number is valid, the brand is authentic, "
        "and the product category matches its registration. "
        "It is safe to purchase."
    ),
    "SUSPICIOUS": (
        "This product raised concerns during verification. "
        "We could not fully confirm its authenticity. "
        "Proceed with caution. If possible, purchase from a "
        "different vendor or verify with NAFDAC directly."
    ),
    "FAKE": (
        "WARNING: This product has FAILED verification. "
        "It shows strong signs of being counterfeit. "
        "Do NOT purchase this product. "
        "Your scan has been logged and reported to NAFDAC."
    ),
    "RESCAN_REQUIRED": (
        "We could not scan this product clearly. "
        "Please hold your phone steady in good lighting and try again."
    ),
}


# Simple instructions (voice-first, non-literate users , Mama Ola)
# Maximum two sentences. No technical language. Direct action.
_SIMPLE_INSTRUCTIONS = {
    "AUTHENTIC":        "This product is real. You can buy it.",
    "SUSPICIOUS":       "We are not sure about this product. Be careful.",
    "FAKE":             "Do not buy this product. It is fake. We have reported it.",
    "RESCAN_REQUIRED":  "We could not read this product clearly. Please try scanning again.",
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
}


def classify(fusion_result: dict) -> dict:
    """
    Maps a fusion engine result to a final user-facing decision.

    Args:
        fusion_result: Output dict from core/fusion_engine.run_fusion()

    Returns:
        ClassificationResult dict:
        {
            "action":             str,   # "BUY" | "CAUTION" | "DO NOT BUY THIS PRODUCT. IT IS A COUNTERFEIT." | "RESCAN"
            "verdict":            str,   # "AUTHENTIC" | "SUSPICIOUS" | "FAKE" | "RESCAN_REQUIRED"
            "final_score":        float | None,
            "severity":           str,
            "confidence_label":   str,
            "report_priority":    str,   # "AUTO" | "PROMPT" | "NONE"
            "instruction":        str,   # Full instruction for N-ATLAS
            "simple_instruction": str,   # Short voice-first instruction
            "atlas_instruction":  str,   # Full instruction + warning appendages
            "override_applied":   bool,
            "override_summary":   str | None,
            "warnings":           list,
            "evidence":           dict,  # Forwarded to evidence_packager
            "breakdown":          dict,  # Score breakdown per signal
            "scan_id":            str,
            "timestamp":          str,
        }
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

        # Override simple instruction for NOT_FOUND; different from a confirmed fake
    reg_status = fusion_result.get("evidence", {}).get("reg_status_code", "")
    if verdict == "FAKE" and reg_status == "NOT_FOUND":
        simple_instruction = (
            "We could not verify this product in our database. "
            "This product may be genuine but "
            "is not yet in our verified product registry. "
            "Check directly with NAFDAC at www.nafdac.gov.ng to confirm."
        )
    else:
        simple_instruction = _SIMPLE_INSTRUCTIONS.get(verdict, _SIMPLE_INSTRUCTIONS["FAKE"])

    # Core classification 
    action           = _ACTION_MAP.get(verdict, "DO NOT BUY THIS PRODUCT. IT IS A COUNTERFEIT.")
    report_priority  = _REPORT_PRIORITY.get(verdict, "AUTO")
    instruction      = _build_instruction(verdict, fusion_result)
    simple_instruction = _SIMPLE_INSTRUCTIONS.get(verdict, _SIMPLE_INSTRUCTIONS["FAKE"])
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
        evidence.get("product_matched_visual") or
        "this product"
    )
    nafdac = evidence.get("nafdac_number", "") or ""
    reg_status = evidence.get("reg_status_code", "") or ""

    # Enrich FAKE instructions with specific failure reason
    if verdict == "FAKE":
        if reg_status == "SUBCATEGORY_MISMATCH":
            registered_cat = (breakdown.get("regulatory", {}).get("nafdac_registered_category") or
                "a different category"
            )
            base += (
                f" The NAFDAC number on this product ({nafdac}) is registered "
                f"for a '{registered_cat}' product - not what you are holding. "
                f"This is a classic counterfeit pattern."
            )
        elif reg_status == "NOT_FOUND":
            nafdac_str = f" '{nafdac}'" if nafdac else ""
            base += (
            f" The NAFDAC number{nafdac_str} could not be verified "
            f"in our current database. This product may be genuine but "
            f"is not yet in our verified product registry. "
            f"Check directly with NAFDAC at www.nafdac.gov.ng to confirm."
            )
        elif reg_status == "EXPIRED":
            base += (
                f" The registration for '{product_name}' has expired. "
                f"This product is no longer authorised for sale in Nigeria."
            )
        elif reg_status == "AGENT_ERROR":
            base += (
                "The NAFDAC verification system could not be reached. "
                "Authenticity cannot be confirmed. Do not purchase this product."
            )
        

    elif verdict == "AUTHENTIC":
        base += f" Confirmed product: {product_name}."

    elif verdict == "SUSPICIOUS":
        # Adds the most specific reason available
        if not evidence.get("nafdac_number"):
            base += (
                " The NAFDAC number could not be read from this label. "
                "A genuine product always has a visible, scannable NAFDAC number."
            )

    return base


def _inject_warnings(instruction: str, warnings: list) -> str:
    """
    Append warning appendages to the atlas_instruction string.
    Each warning type in _WARNING_APPENDAGES is appended once if present.
    Preserves insertion order, most critical warnings appear first.

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


