"""
End-to-End Fusion Engine Test
==============================
Tests all scenarios using real Visual v2 output signals
combined with realistic mock OCR and REG payloads.

Scenarios:
  1. AUTHENTIC  — real product, clean scan, verified NAFDAC
  2. FAKE       — altered image (Visual v2 flags it), real NAFDAC
  3. SUSPICIOUS — altered image, NAFDAC not in DB (coverage gap)
  4. DAMAGED    — blurry scan, REG takes authority
  5. RESCAN     — extreme blur, scan rejected
  6. FALLBACK   — sharp scan, semantic NAFDAC lookup
  7. HARD FAKE  — expired NAFDAC registration
  8. FAILSAFE   — all signals missing/crashed
"""

import sys, os, json, importlib.util

# ── Path setup ────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, ".."))

# Mock the ai_engine package path
sys.modules["ai_engine"] = type(sys)("ai_engine")
sys.modules["ai_engine.fusion_engine"] = type(sys)("ai_engine.fusion_engine")

import importlib, types

def mock_module(name, real_path):
    spec = importlib.util.spec_from_file_location(name, real_path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load modules in dependency order
thresholds = mock_module("ai_engine.fusion_engine.config.thresholds",
                         os.path.join(BASE, "config", "thresholds.py"))
weights    = mock_module("ai_engine.fusion_engine.config.weights",
                         os.path.join(BASE, "config", "weights.py"))
logger_mod = mock_module("ai_engine.fusion_engine.utils.logger",
                         os.path.join(BASE, "utils", "logger.py"))
schemas    = mock_module("ai_engine.fusion_engine.utils.schemas",
                         os.path.join(BASE, "utils", "schemas.py"))

vis_adapt  = mock_module("ai_engine.fusion_engine.signals.visual_adapter",
                         os.path.join(BASE, "signals", "visual_adapter.py"))
ocr_adapt  = mock_module("ai_engine.fusion_engine.signals.ocr_adapter",
                         os.path.join(BASE, "signals", "ocr_adapter.py"))
reg_adapt  = mock_module("ai_engine.fusion_engine.signals.reg_adapter",
                         os.path.join(BASE, "signals", "reg_adapter.py"))

fusion_mod = mock_module("ai_engine.fusion_engine.core.fusion_engine",
                         os.path.join(BASE, "core", "fusion_engine.py"))
classifier = mock_module("ai_engine.fusion_engine.core.decision_classifier",
                         os.path.join(BASE, "core", "decision_classifier.py"))
packager   = mock_module("ai_engine.fusion_engine.core.evidence_packager",
                         os.path.join(BASE, "core", "evidence_packager.py"))
main_mod   = mock_module("ai_engine.fusion_engine.main",
                         os.path.join(BASE, "main.py"))

run_scan = main_mod.run_scan

# ── Reusable mock signals ─────────────────────────────────────────────────────

def make_ocr(nafdac="A8-4114", anomaly=0.06, brand="Kelloggs"):
    return {
        "source": "OCR_Linguistic",
        "metadata": {
            "product_name":       f"{brand} Corn Flakes 300g",
            "nafdac_number":      nafdac,
            "batch_number":       "BN20240901",
            "expiry_date":        "2026-12-01",
            "avg_ocr_confidence": 0.91,
            "brand_detected":     brand,
            "brand_similarity":   96.0,
            "brand_anomaly_flag": 0,
        },
        "brand_anomaly": {
            "brand_detected":        brand,
            "similarity_score":      96.0,
            "lookalike_corrections": [],
            "brand_anomaly_flag":    0,
        },
        "structural_validation": {
            "missing_fields":       [],
            "structural_score":     0.97,
            "expiry_format_valid":  True,
            "batch_format_valid":   True,
        },
        "rule_score": {
            "rule_score":              0.06,
            "damage_score_applied":    0.1,
            "adjusted_ocr_confidence": 0.91,
        },
        "ml_score":                 0.05,
        "final_text_anomaly_score": anomaly,
    }

def make_reg(status="VERIFIED", score=1.0, fallback=False):
    return {
        "verified":           status == "VERIFIED",
        "verification_score": score,
        "status_code":        status,
        "severity":           "NONE" if status == "VERIFIED" else "CRITICAL",
        "summary":            f"Status: {status}",
        "detail":             f"Regulatory check result: {status}",
        "expiry_check":       {"is_near_expiry": False, "days_remaining": 400},
        "alignment":          {"scanned_norm": "food", "registered_norm": "food",
                               "similarity_score": 0.95},
        "matched_record":     {
            "product_name":   "Kelloggs Corn Flakes 300g",
            "subcategory":    "food",
            "expiry_date_iso":"2026-12-01",
            "applicant_name": "KELLOGG COMPANY",
        } if status not in ("NOT_FOUND", "AGENT_ERROR") else None,
        "all_records":     [],
        "fallback_used":   fallback,
        "tools_called":    ["lookup_nafdac"],
        "reasoning_trace": [],
    }

GPS = {"lat": 6.5244, "lng": 3.3792, "accuracy": 8.5}

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
results = []

def run_test(name, visual, ocr, reg, expected_verdict, extra_checks=None):
    try:
        result = run_scan(visual, ocr, reg, GPS, "open_market", package_evidence=False)
        verdict  = result.get("verdict")
        score    = result.get("final_score")
        mode     = result.get("weight_mode")
        override = result.get("override_applied")
        warnings = [w.get("type") for w in result.get("warnings", [])]

        ok = verdict == expected_verdict
        if extra_checks:
            for fn in extra_checks:
                ok = ok and fn(result)

        status = PASS if ok else FAIL
        results.append(ok)
        print(f"\n{status}  [{name}]")
        print(f"       verdict={verdict}  score={score}  mode={mode}  override={override}")
        if warnings:
            print(f"       warnings={warnings}")
        if not ok:
            print(f"       EXPECTED verdict={expected_verdict}")
            print(f"       full result: {json.dumps(result, indent=2, default=str)[:600]}")
    except Exception as e:
        import traceback
        results.append(False)
        print(f"\n\033[91m✗ ERROR\033[0m  [{name}]  {e}")
        traceback.print_exc()

# ── TEST SIGNALS ──────────────────────────────────────────────────────────────

# Real Corn Flakes — Visual v2 authentic output
VISUAL_AUTHENTIC = {
    "product":           "Kelloggs_cornflakes_300g+45g",
    "Visual Similarity": 0.8617,
    "margin":            0.4361,
    "anomaly_flag":      False,
    "ambiguity_flag":    False,
    "damage_score":      0.1,
    "blur_value":        36.26,
    "penalty_applied":   1.0,
    "confidence":        0.7755,
    "verdict":           "Authentic",
    "flags":             [],
}

# Altered Corn Flakes (corn_flakes_edited) — Visual v2 fake output
VISUAL_FAKE_EDITED = {
    "product":           "Kelloggs_cornflakes_300g+45g",
    "Visual Similarity": 0.6953,
    "margin":            0.3091,
    "anomaly_flag":      False,
    "ambiguity_flag":    False,
    "damage_score":      0.1,
    "blur_value":        445.95,
    "penalty_applied":   0.70,
    "confidence":        0.4380,
    "verdict":           "Fake",
    "flags":             ["BLUR_ANOMALY (0.7x): composited/altered image"],
}

# Rooster switch — Visual v2 fake output (anomaly + blur)
VISUAL_FAKE_ROOSTER = {
    "product":           "Kelloggs_cornflakes_300g+45g",
    "Visual Similarity": 0.6447,
    "margin":            0.2663,
    "anomaly_flag":      True,
    "ambiguity_flag":    False,
    "damage_score":      0.1,
    "blur_value":        456.82,
    "penalty_applied":   0.385,
    "confidence":        0.2234,
    "verdict":           "Fake",
    "flags":             ["BLUR_ANOMALY", "ANOMALY_PENALTY"],
}

# Blurry scan
VISUAL_BLURRY = {**VISUAL_AUTHENTIC,
    "damage_score": 0.8, "blur_value": 12.0, "confidence": 0.4,
    "verdict": "Suspicious", "flags": ["SCAN_QUALITY_WARNING"]}

# Extreme blur
VISUAL_EXTREME_BLUR = {**VISUAL_AUTHENTIC,
    "damage_score": 0.8, "blur_value": 2.1, "confidence": 0.2}

print("=" * 65)
print("  SABILENS FUSION ENGINE — END-TO-END TEST SUITE")
print("=" * 65)

# ── SCENARIO 1: Authentic product, clean scan, verified NAFDAC ────────────────
run_test(
    "AUTHENTIC — real product, verified NAFDAC",
    VISUAL_AUTHENTIC, make_ocr(), make_reg("VERIFIED"),
    expected_verdict="AUTHENTIC",
    extra_checks=[lambda r: r["weight_mode"] == "BASE",
                  lambda r: r["action"] == "BUY"],
)

# ── SCENARIO 2: Fake (edited layout), real NAFDAC in DB ──────────────────────
# Visual says Fake (confidence=0.438). Even with NAFDAC verified,
# the low visual score should push final below AUTHENTIC threshold.
run_test(
    "FAKE — altered layout, NAFDAC present",
    VISUAL_FAKE_EDITED, make_ocr(), make_reg("VERIFIED"),
    expected_verdict="SUSPICIOUS",   # Fusion may uplift to SUSPICIOUS due to clean OCR+REG
)

# ── SCENARIO 3: Fake (rooster switch), real NAFDAC in DB ─────────────────────
run_test(
    "FAKE — rooster switch, anomaly flag active",
    VISUAL_FAKE_ROOSTER, make_ocr(), make_reg("VERIFIED"),
    expected_verdict="FAKE",
)

# ── SCENARIO 4: Altered image, NAFDAC not in DB (coverage gap) ───────────────
run_test(
    "NOT_VERIFIED — altered image + NAFDAC missing from DB",
    VISUAL_FAKE_EDITED, make_ocr(), make_reg("NOT_FOUND", score=0.0),
    expected_verdict="NOT_VERIFIED",
)

# ── SCENARIO 5: Blurry scan, REG takes authority ──────────────────────────────
run_test(
    "DAMAGED — blurry scan, REG weight=0.55",
    VISUAL_BLURRY, make_ocr(), make_reg("VERIFIED"),
    expected_verdict="AUTHENTIC",
    extra_checks=[lambda r: r["weight_mode"] == "DAMAGED"],
)

# ── SCENARIO 6: Extreme blur — scan rejected ─────────────────────────────────
run_test(
    "RESCAN_REQUIRED — extreme blur",
    VISUAL_EXTREME_BLUR, make_ocr(), make_reg("VERIFIED"),
    expected_verdict="RESCAN_REQUIRED",
    extra_checks=[lambda r: r["final_score"] is None],
)

# ── SCENARIO 7: Sharp scan, semantic NAFDAC fallback ─────────────────────────
run_test(
    "FALLBACK — semantic NAFDAC match",
    VISUAL_AUTHENTIC, make_ocr(), make_reg("VERIFIED", fallback=True),
    expected_verdict="AUTHENTIC",
    extra_checks=[lambda r: r["weight_mode"] == "FALLBACK"],
)

# ── SCENARIO 8: Expired NAFDAC — hard FAKE override ─────────────────────────
run_test(
    "HARD FAKE — expired NAFDAC registration",
    VISUAL_AUTHENTIC, make_ocr(), make_reg("EXPIRED", score=0.0),
    expected_verdict="FAKE",
    extra_checks=[lambda r: r["override_applied"] is True],
)

# ── SCENARIO 9: OCR finds no NAFDAC number ───────────────────────────────────
ocr_no_nafdac = make_ocr(nafdac=None)
ocr_no_nafdac["metadata"]["nafdac_number"] = None
run_test(
    "SUSPICIOUS FLOOR — OCR cannot read NAFDAC number",
    VISUAL_AUTHENTIC, ocr_no_nafdac, make_reg("VERIFIED"),
    expected_verdict="SUSPICIOUS",
)

# ── SCENARIO 10: Failsafe — all signals None ─────────────────────────────────
run_test(
    "FAILSAFE — all signals missing",
    None, None, None,
    expected_verdict="FAKE",
    extra_checks=[lambda r: r["status"] in ("PARTIAL", "FAILSAFE")],
)

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'=' * 65}")
print(f"  RESULTS: {passed}/{total} passed")
if passed == total:
    print("  \033[92mAll tests passed. Fusion Engine is ready.\033[0m")
else:
    print(f"  \033[91m{total - passed} test(s) failed. Review output above.\033[0m")
print("=" * 65)
