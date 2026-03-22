"""
Fusion Engine — Stronger Test Suite
=====================================

Deeper correctness tests that go beyond the smoke-level checks in
test_fusion_engine.py.  Every test targets a specific, named behaviour
that could silently regress without being caught by the existing suite.

Groups:
  A — Exact verdict boundary scores    (threshold precision)
  B — Weight formula correctness        (exact math, all three modes)
  C — Override hierarchy & priority     (REG beats VISUAL/OCR; SUSPICIOUS_FLOOR logic)
  D — Instruction content               (what text each verdict puts in instructions)
  E — Warning injection                 (atlas_instruction appendages)
  F — Evidence packager deep tests      (hash, fingerprint flags, channels, GPS)
  G — Confidence label bands            (all five bands + boundary values)
  H — Validate functions                (reg / visual / ocr input validation)
  I — RESCAN_REQUIRED complete path     (all required fields, save_for_retraining)
  J — Full pipeline edge cases          (run_scan end-to-end, UUID4 scan_id format)

Run:
    pytest ai_engine/fusion_engine/test/test_fusion_strong.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ai_engine.fusion_engine.signals.visual_adapter import adapt as visual_adapt, validate as visual_validate
from ai_engine.fusion_engine.signals.ocr_adapter    import adapt as ocr_adapt,    validate as ocr_validate
from ai_engine.fusion_engine.signals.reg_adapter    import adapt as reg_adapt,    validate as reg_validate
from ai_engine.fusion_engine.core.fusion_engine     import run_fusion
from ai_engine.fusion_engine.core.decision_classifier import classify
from ai_engine.fusion_engine.core.evidence_packager  import package
from ai_engine.fusion_engine.main                    import run_scan
from ai_engine.fusion_engine.config.thresholds      import (
    THRESHOLD_AUTHENTIC, THRESHOLD_SUSPICIOUS, SUSPICIOUS_FLOOR_SCORE,
    EXTREME_BLUR_CEILING, DAMAGED_SCORE_FLOOR,
    get_verdict, get_confidence_label, get_severity,
)
from ai_engine.fusion_engine.config.weights import (
    SIGNAL_WEIGHTS, SIGNAL_WEIGHTS_DAMAGED, SIGNAL_WEIGHTS_FALLBACK, validate_weights,
)


# ── Shared minimal signal factories ───────────────────────────────────────────

def make_visual(conf=0.79, sim=0.88, damage=0.1, blur=80.0,
                product="Vaseline Blue Seal 225ml"):
    verdict = "Authentic" if conf >= 0.75 else "Suspicious" if conf >= 0.45 else "Fake"
    return {
        "product":           product,
        "Visual Similarity": sim,
        "damage_score":      damage,
        "blur_value":        blur,
        "confidence":        conf,
        "verdict":           verdict,
    }


def make_ocr(anomaly=0.06, nafdac="02-0385", lookalikes=None,
             brand="Vaseline", brand_flag=0):
    return {
        "source": "OCR_Linguistic",
        "metadata": {
            "nafdac_number":      nafdac,
            "avg_ocr_confidence": 0.91,
            "brand_detected":     brand,
            "brand_similarity":   95.0,
            "brand_anomaly_flag": brand_flag,
        },
        "brand_anomaly": {
            "brand_detected":        brand,
            "closest_match":         brand,
            "similarity_score":      95.0,
            "lookalike_corrections": lookalikes or [],
            "brand_anomaly_flag":    brand_flag,
        },
        "structural_validation": {
            "missing_fields":      [],
            "structural_score":    1.0,
            "expiry_format_valid": True,
            "batch_format_valid":  True,
        },
        "rule_score": {
            "rule_score":              anomaly,
            "components":              {},
            "damage_score_applied":    0.1,
            "adjusted_ocr_confidence": 0.91,
        },
        "ml_score":                 anomaly,
        "final_text_anomaly_score": anomaly,
    }


def make_reg(score=1.0, status="VERIFIED", severity="NONE", verified=True,
             scanned_cat="Cosmetics", reg_cat="Cosmetics",
             near_expiry=False, days=900):
    return {
        "verified":           verified,
        "verification_score": score,
        "status_code":        status,
        "severity":           severity,
        "summary":            f"Test: {status}",
        "detail":             f"Detail for {status}",
        "expiry_check": {
            "is_valid":       True,
            "is_near_expiry": near_expiry,
            "days_remaining": days,
            "severity":       "WARNING" if near_expiry else "NONE",
            "message":        "Expiring soon." if near_expiry else "Valid.",
        },
        "alignment": {
            "is_match":        scanned_cat == reg_cat,
            "scanned_norm":    scanned_cat,
            "registered_norm": reg_cat,
        },
        "matched_record": {
            "product_name":    "Vaseline Blue Seal",
            "subcategory":     reg_cat,
            "expiry_date_iso": "2028-12-20",
            "applicant_name":  "Unilever Nigeria PLC",
        },
        "all_records":     [],
        "fallback_used":   False,
        "tools_called":    ["lookup_nafdac", "check_expiry", "check_alignment"],
        "reasoning_trace": [],
    }


GPS = {"lat": 6.5244, "lng": 3.3792, "accuracy": 8.5}


def _fuse(visual_kw=None, ocr_kw=None, reg_kw=None):
    return run_fusion(
        visual_adapt(make_visual(**(visual_kw or {}))),
        ocr_adapt(make_ocr(**(ocr_kw or {}))),
        reg_adapt(make_reg(**(reg_kw or {}))),
    )


# ── GROUP A: Exact Verdict Boundaries ─────────────────────────────────────────

class TestVerdictBoundaries:
    """Verify exact threshold boundaries — ensures thresholds.py values are honoured."""

    def test_score_exactly_at_authentic_threshold_is_authentic(self):
        """score == 0.72 → AUTHENTIC (>= threshold)."""
        r = _fuse(
            visual_kw={"conf": THRESHOLD_AUTHENTIC, "sim": 0.9},
            ocr_kw={"anomaly": round(1.0 - THRESHOLD_AUTHENTIC, 6)},
            reg_kw={"score": THRESHOLD_AUTHENTIC},
        )
        assert r["verdict"] == "AUTHENTIC"
        assert r["final_score"] == pytest.approx(THRESHOLD_AUTHENTIC, abs=0.001)

    def test_score_just_below_authentic_threshold_is_suspicious(self):
        """score == 0.71 → SUSPICIOUS (< 0.72)."""
        below = 0.71
        r = _fuse(
            visual_kw={"conf": below, "sim": 0.9},
            ocr_kw={"anomaly": round(1.0 - below, 6)},
            reg_kw={"score": below},
        )
        assert r["verdict"] == "SUSPICIOUS"
        assert r["final_score"] == pytest.approx(below, abs=0.001)

    def test_score_exactly_at_suspicious_floor_is_suspicious(self):
        """score == 0.45 → SUSPICIOUS (>= 0.45, not yet FAKE)."""
        r = _fuse(
            visual_kw={"conf": THRESHOLD_SUSPICIOUS, "sim": 0.9},
            ocr_kw={"anomaly": round(1.0 - THRESHOLD_SUSPICIOUS, 6)},
            reg_kw={"score": THRESHOLD_SUSPICIOUS},
        )
        assert r["verdict"] == "SUSPICIOUS"
        assert r["final_score"] == pytest.approx(THRESHOLD_SUSPICIOUS, abs=0.001)

    def test_score_just_below_suspicious_floor_is_fake(self):
        """score == 0.44 → FAKE (< 0.45)."""
        below = 0.44
        r = _fuse(
            visual_kw={"conf": below, "sim": 0.9},
            ocr_kw={"anomaly": round(1.0 - below, 6)},
            reg_kw={"score": below},
        )
        assert r["verdict"] == "FAKE"
        assert r["final_score"] == pytest.approx(below, abs=0.001)

    def test_get_verdict_exact_boundary_values(self):
        """get_verdict() must respect the exact threshold constants."""
        assert get_verdict(1.00)  == "AUTHENTIC"
        assert get_verdict(0.72)  == "AUTHENTIC"   # exactly at threshold
        assert get_verdict(0.719) == "SUSPICIOUS"  # just below
        assert get_verdict(0.45)  == "SUSPICIOUS"  # at lower boundary
        assert get_verdict(0.449) == "FAKE"        # just below
        assert get_verdict(0.00)  == "FAKE"

    def test_severity_maps_correctly_for_all_verdicts(self):
        assert get_severity("AUTHENTIC")  == "NONE"
        assert get_severity("SUSPICIOUS") == "MEDIUM"
        assert get_severity("FAKE")       == "CRITICAL"
        # Unknown verdict should default to CRITICAL (safe default)
        assert get_severity("UNKNOWN_VERDICT") == "CRITICAL"


# ── GROUP B: Weight Formula Correctness ───────────────────────────────────────

class TestWeightFormula:
    """Verify exact weight values and weighted-score arithmetic for all three modes."""

    def test_all_weight_sets_sum_to_exactly_one(self):
        """validate_weights() raises ValueError if any set is misconfigured."""
        validate_weights()   # raises on failure — test passes if silent

    def test_base_weight_values_are_correct(self):
        assert SIGNAL_WEIGHTS["visual"] == pytest.approx(0.40)
        assert SIGNAL_WEIGHTS["ocr"]    == pytest.approx(0.35)
        assert SIGNAL_WEIGHTS["reg"]    == pytest.approx(0.25)

    def test_damaged_weight_values_are_correct(self):
        assert SIGNAL_WEIGHTS_DAMAGED["visual"] == pytest.approx(0.15)
        assert SIGNAL_WEIGHTS_DAMAGED["ocr"]    == pytest.approx(0.30)
        assert SIGNAL_WEIGHTS_DAMAGED["reg"]    == pytest.approx(0.55)

    def test_fallback_weight_values_are_correct(self):
        assert SIGNAL_WEIGHTS_FALLBACK["visual"] == pytest.approx(0.475)
        assert SIGNAL_WEIGHTS_FALLBACK["ocr"]    == pytest.approx(0.425)
        assert SIGNAL_WEIGHTS_FALLBACK["reg"]    == pytest.approx(0.10)

    def test_breakdown_weighted_scores_sum_to_final_score(self):
        """The three weighted scores in breakdown must always add up to final_score."""
        r = _fuse()
        total = sum(r["breakdown"][s]["weighted"] for s in ["visual", "ocr", "reg"])
        assert total == pytest.approx(r["final_score"], abs=0.001)

    def test_base_formula_only_visual_contributes(self):
        """visual=1.0, ocr=0.0, reg=0.0, BASE → final_score = 0.40 (visual weight)."""
        r = run_fusion(
            visual_adapt(make_visual(conf=1.0, sim=0.9)),
            ocr_adapt(make_ocr(anomaly=1.0)),   # ocr_score = 0.0
            reg_adapt(make_reg(score=0.0, status="NOT_FOUND",
                               severity="CRITICAL", verified=False)),
        )
        assert r["weight_mode"] == "BASE"
        assert r["final_score"] == pytest.approx(0.40, abs=0.01)
        assert r["verdict"] == "FAKE"   # 0.40 < THRESHOLD_SUSPICIOUS

    def test_damaged_mode_reg_dominates_when_visual_zero(self):
        """With DAMAGED weights, reg=1.0 alone → score = 0.55 (reg weight is 0.55)."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.0, sim=0.5, damage=0.4, blur=20.0)),
            ocr_adapt(make_ocr(anomaly=1.0)),   # ocr_score = 0.0
            reg_adapt(make_reg(score=1.0)),
        )
        assert r["weight_mode"] == "DAMAGED"
        assert r["final_score"] == pytest.approx(0.55, abs=0.01)
        assert r["verdict"] == "SUSPICIOUS"

    def test_fallback_mode_visual_and_ocr_lead(self):
        """With FALLBACK weights, visual+ocr dominate (0.475+0.425=0.90 together)."""
        reg_fallback = make_reg()
        reg_fallback["fallback_used"] = True
        r = run_fusion(
            visual_adapt(make_visual(conf=0.9, sim=0.9)),
            ocr_adapt(make_ocr(anomaly=0.0)),   # ocr_score = 1.0
            reg_adapt(reg_fallback),
        )
        assert r["weight_mode"] == "FALLBACK"
        # visual*0.475 + ocr*1.0*0.425 + reg*0.10 ≈ 0.9*0.475 + 1.0*0.425 + score*0.10
        assert r["final_score"] > 0.85

    def test_damage_threshold_boundary_is_exact(self):
        """damage_score == DAMAGED_SCORE_FLOOR triggers DAMAGED mode (>= not >)."""
        r_at = _fuse(visual_kw={"conf": 0.8, "sim": 0.9,
                                 "damage": DAMAGED_SCORE_FLOOR, "blur": 50.0})
        assert r_at["weight_mode"] == "DAMAGED"

        r_below = _fuse(visual_kw={"conf": 0.8, "sim": 0.9,
                                    "damage": DAMAGED_SCORE_FLOOR - 0.01, "blur": 50.0})
        assert r_below["weight_mode"] == "BASE"

    def test_breakdown_weight_values_match_selected_mode(self):
        """The weights stored in breakdown must match the selected weight set."""
        r = _fuse(visual_kw={"damage": 0.1})   # BASE mode
        assert r["breakdown"]["visual"]["weight"] == pytest.approx(SIGNAL_WEIGHTS["visual"])
        assert r["breakdown"]["ocr"]["weight"]    == pytest.approx(SIGNAL_WEIGHTS["ocr"])
        assert r["breakdown"]["reg"]["weight"]    == pytest.approx(SIGNAL_WEIGHTS["reg"])


# ── GROUP C: Override Hierarchy & Priority ─────────────────────────────────────

class TestOverrideHierarchy:
    """REG hard override (priority 1) must always beat VISUAL/OCR soft override (priority 2)."""

    def test_reg_override_wins_over_visual_low_similarity(self):
        """AGENT_ERROR forces FAKE even when visual also has low-sim override."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.9, sim=0.05)),   # visual override fires (sim < 0.20)
            ocr_adapt(make_ocr()),
            reg_adapt(make_reg(score=0.0, status="AGENT_ERROR",
                               severity="CRITICAL", verified=False)),
        )
        assert r["verdict"] == "FAKE"
        assert r["override_applied"] is True
        assert r["applied_override"]["source"] == "REG"
        assert r["applied_override"]["type"] == "HARD_FAKE"

    def test_suspicious_floor_fires_when_weighted_score_above_threshold(self):
        """OCR override + strong visual/reg → raw_weighted ≥ 0.45 → floor to SUSPICIOUS."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.95, sim=0.9)),
            ocr_adapt(make_ocr(nafdac=None, anomaly=0.06)),   # OCR override; fusion_score=0.94
            reg_adapt(make_reg(score=1.0)),
        )
        assert r["verdict"] == "SUSPICIOUS"
        assert r["final_score"] == pytest.approx(SUSPICIOUS_FLOOR_SCORE, abs=0.001)
        assert r["override_applied"] is True
        assert r["applied_override"]["type"] == "SUSPICIOUS_FLOOR"

    def test_ocr_override_does_not_prevent_fake_when_score_already_below_floor(self):
        """If raw_weighted < 0.45 even with overrides, SUSPICIOUS_FLOOR does NOT fire.
        Verdict falls through to FAKE naturally."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.2, sim=0.9)),    # low visual, no sim override
            ocr_adapt(make_ocr(nafdac=None, anomaly=0.8)),   # OCR override, low score
            reg_adapt(make_reg(score=0.0, status="NOT_FOUND",
                               severity="CRITICAL", verified=False)),
        )
        # visual=0.2, ocr=0.2, reg=0.0, BASE → 0.2*0.40 + 0.2*0.35 + 0.0*0.25 = 0.15 < 0.45
        assert r["verdict"] == "FAKE"
        assert r["override_applied"] is False  # SUSPICIOUS_FLOOR did NOT fire

    def test_expired_is_hard_override_beats_perfect_signals(self):
        """EXPIRED must force FAKE regardless of visual=1.0 and OCR=perfect."""
        r = _fuse(
            visual_kw={"conf": 1.0, "sim": 1.0},
            ocr_kw={"anomaly": 0.0},
            reg_kw={"score": 0.1, "status": "EXPIRED", "severity": "HIGH", "verified": False},
        )
        assert r["verdict"] == "FAKE"
        assert r["override_applied"] is True

    def test_visual_low_sim_source_label_is_visual(self):
        """When only visual override fires, applied_override.source = 'VISUAL'."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.9, sim=0.05)),   # visual override
            ocr_adapt(make_ocr()),
            reg_adapt(make_reg()),
        )
        assert r["applied_override"]["source"] == "VISUAL"

    def test_ocr_missing_nafdac_source_label_is_ocr(self):
        """When only OCR override fires, applied_override.source = 'OCR'."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.9, sim=0.9)),   # no visual override
            ocr_adapt(make_ocr(nafdac=None)),
            reg_adapt(make_reg()),
        )
        assert r["applied_override"]["source"] == "OCR"

    def test_all_overrides_list_tracks_all_fired_sources(self):
        """all_overrides must list every source that set override_flag=True."""
        r = run_fusion(
            visual_adapt(make_visual(conf=0.9, sim=0.05)),   # visual fires
            ocr_adapt(make_ocr(nafdac=None)),                # ocr fires
            reg_adapt(make_reg(score=0.0, status="AGENT_ERROR",
                               severity="CRITICAL", verified=False)),  # reg fires
        )
        sources = [o["source"] for o in r["all_overrides"]]
        assert "REG" in sources
        assert "VISUAL" in sources
        assert "OCR" in sources

    def test_no_override_applied_flag_false_for_clean_scan(self):
        r = _fuse()
        assert r["override_applied"] is False
        assert r["applied_override"] is None


# ── GROUP D: Instruction Content ──────────────────────────────────────────────

class TestInstructionContent:
    """_build_instruction() must enrich the base template with verdict-specific details."""

    def _clf(self, visual_kw=None, ocr_kw=None, reg_kw=None):
        return classify(_fuse(visual_kw=visual_kw, ocr_kw=ocr_kw, reg_kw=reg_kw))

    def test_authentic_instruction_contains_confirmed_product(self):
        clf = self._clf()
        assert "Confirmed product:" in clf["instruction"]

    def test_suspicious_missing_nafdac_instruction_names_nafdac(self):
        clf = self._clf(ocr_kw={"nafdac": None})
        assert "NAFDAC number" in clf["instruction"]

    def test_fake_agent_error_instruction_references_system_unavailable(self):
        clf = self._clf(reg_kw={"score": 0.0, "status": "AGENT_ERROR",
                                "severity": "CRITICAL", "verified": False})
        assert "could not be reached" in clf["instruction"]

    def test_fake_expired_instruction_references_expiry(self):
        clf = self._clf(reg_kw={"score": 0.1, "status": "EXPIRED",
                                "severity": "HIGH", "verified": False})
        assert "expired" in clf["instruction"].lower()

    def test_simple_instruction_authentic_says_buy(self):
        clf = self._clf()
        assert "buy" in clf["simple_instruction"].lower()

    def test_simple_instruction_fake_says_do_not_buy(self):
        clf = self._clf(reg_kw={"score": 0.0, "status": "AGENT_ERROR",
                                "severity": "CRITICAL", "verified": False})
        assert "not buy" in clf["simple_instruction"].lower()

    def test_simple_instruction_suspicious_conveys_caution(self):
        clf = self._clf(ocr_kw={"nafdac": None})
        assert any(word in clf["simple_instruction"].lower()
                   for word in ["careful", "not sure", "caution"])

    def test_rescan_required_action_is_rescan(self):
        """RESCAN_REQUIRED must produce action='RESCAN', not 'DO NOT BUY'."""
        fusion_result = _fuse(visual_kw={"conf": 0.5, "sim": 0.6,
                                          "damage": 0.8, "blur": 3.0})
        assert fusion_result["verdict"] == "RESCAN_REQUIRED"
        clf = classify(fusion_result)
        assert clf["action"] == "RESCAN"
        assert clf["report_priority"] == "NONE"

    def test_instruction_is_never_empty_string(self):
        """Every verdict must produce a non-empty instruction."""
        for reg_kw, ocr_kw in [
            (None, None),
            ({"score": 0.0, "status": "AGENT_ERROR", "severity": "CRITICAL", "verified": False}, None),
            (None, {"nafdac": None}),
        ]:
            clf = self._clf(reg_kw=reg_kw, ocr_kw=ocr_kw)
            assert len(clf["instruction"]) > 20, f"Empty instruction for verdict={clf['verdict']}"


# ── GROUP E: Warning Injection ─────────────────────────────────────────────────

class TestWarningInjection:
    """atlas_instruction must be enriched with all applicable warning appendages."""

    def _clf(self, visual_kw=None, ocr_kw=None, reg_kw=None):
        return classify(_fuse(visual_kw=visual_kw, ocr_kw=ocr_kw, reg_kw=reg_kw))

    def test_near_expiry_appendage_in_atlas_instruction(self):
        clf = self._clf(reg_kw={"score": 0.85, "status": "VERIFIED_NEAR_EXPIRY",
                                "severity": "WARNING", "verified": True,
                                "near_expiry": True, "days": 25})
        assert "expiring soon" in clf["atlas_instruction"].lower()

    def test_lookalike_chars_appendage_in_atlas_instruction(self):
        clf = self._clf(ocr_kw={"lookalikes": ["0 → o"]})
        assert "character substitutions" in clf["atlas_instruction"].lower()

    def test_low_scan_quality_appendage_when_damaged_mode(self):
        clf = self._clf(visual_kw={"conf": 0.6, "sim": 0.7, "damage": 0.4, "blur": 16.0})
        assert "scan quality" in clf["atlas_instruction"].lower()

    def test_semantic_fallback_appendage_when_fallback_used(self):
        reg = make_reg()
        reg["fallback_used"] = True
        clf = classify(run_fusion(
            visual_adapt(make_visual()),
            ocr_adapt(make_ocr()),
            reg_adapt(reg),
        ))
        assert "NAFDAC number could not be matched exactly" in clf["atlas_instruction"]

    def test_multiple_warnings_both_appended(self):
        """NEAR_EXPIRY + LOOKALIKE both inject into atlas_instruction."""
        clf = self._clf(
            ocr_kw={"lookalikes": ["1 → l"]},
            reg_kw={"score": 0.85, "status": "VERIFIED_NEAR_EXPIRY",
                    "severity": "WARNING", "verified": True,
                    "near_expiry": True, "days": 10},
        )
        assert "expiring soon" in clf["atlas_instruction"].lower()
        assert "character substitutions" in clf["atlas_instruction"].lower()

    def test_atlas_instruction_includes_base_instruction_text(self):
        """The base verdict instruction must appear before any appendages."""
        clf = self._clf()
        assert "passed all verification checks" in clf["atlas_instruction"]

    def test_clean_scan_atlas_equals_instruction_with_confirmed(self):
        """For a clean AUTHENTIC scan with no warnings, atlas adds 'Confirmed product:'."""
        clf = self._clf()
        assert "Confirmed product:" in clf["atlas_instruction"]


# ── GROUP F: Evidence Packager Deep Tests ─────────────────────────────────────

class TestEvidencePackagerDeep:

    def _ep(self, visual_kw=None, ocr_kw=None, reg_kw=None,
            channel="open_market", gps=None):
        clf = classify(_fuse(visual_kw=visual_kw, ocr_kw=ocr_kw, reg_kw=reg_kw))
        return package(clf, gps_coordinates=gps or GPS, purchase_channel=channel)

    def _fake_reg(self):
        return {"score": 0.0, "status": "AGENT_ERROR", "severity": "CRITICAL", "verified": False}

    def test_integrity_hash_is_64_lowercase_hex(self):
        ep = self._ep(reg_kw=self._fake_reg())
        h = ep["integrity_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_two_scans_produce_different_scan_ids(self):
        """UUID4 scan_ids must never collide."""
        ep1 = self._ep(reg_kw=self._fake_reg())
        ep2 = self._ep(reg_kw=self._fake_reg())
        assert ep1["scan_id"] != ep2["scan_id"]

    def test_all_valid_purchase_channels_accepted(self):
        valid = ["traffic_vendor", "roadside_store", "open_market",
                 "supermarket", "supplier", "online", "unknown"]
        for ch in valid:
            ep = self._ep(reg_kw=self._fake_reg(), channel=ch)
            assert ep["purchase_channel"] == ch, f"Channel {ch!r} was rejected unexpectedly"

    def test_invalid_purchase_channel_is_sanitised_to_unknown(self):
        ep = self._ep(reg_kw=self._fake_reg(), channel="pavement_vendor")
        assert ep["purchase_channel"] == "unknown"

    def test_fingerprint_agent_error_flag_true(self):
        ep = self._ep(reg_kw=self._fake_reg())
        lbl = ep["fingerprint"]["label_anomalies"]
        assert lbl["nafdac_agent_error"] is True
        assert lbl["registration_expired"] is False
        assert lbl["nafdac_not_found"] is False
        assert lbl["nafdac_category_mismatch"] is False

    def test_fingerprint_expired_flag_true(self):
        ep = self._ep(reg_kw={"score": 0.1, "status": "EXPIRED",
                               "severity": "HIGH", "verified": False})
        lbl = ep["fingerprint"]["label_anomalies"]
        assert lbl["registration_expired"] is True
        assert lbl["nafdac_agent_error"] is False

    def test_fingerprint_not_found_flag_true(self):
        ep = self._ep(reg_kw={"score": 0.0, "status": "NOT_FOUND",
                               "severity": "CRITICAL", "verified": False})
        assert ep["fingerprint"]["label_anomalies"]["nafdac_not_found"] is True

    def test_fingerprint_category_mismatch_flag_true(self):
        ep = self._ep(reg_kw={"score": 0.2, "status": "SUBCATEGORY_MISMATCH",
                               "severity": "CRITICAL", "verified": False})
        assert ep["fingerprint"]["label_anomalies"]["nafdac_category_mismatch"] is True

    def test_fingerprint_lookalike_flag_when_corrections_present(self):
        ep = self._ep(ocr_kw={"lookalikes": ["0 → o"]}, reg_kw=self._fake_reg())
        lbl = ep["fingerprint"]["label_anomalies"]
        assert lbl["lookalike_chars_detected"] is True
        assert "0 → o" in lbl["lookalike_corrections"]

    def test_fingerprint_lookalike_flag_false_when_no_corrections(self):
        ep = self._ep(reg_kw=self._fake_reg())
        assert ep["fingerprint"]["label_anomalies"]["lookalike_chars_detected"] is False

    def test_nafdac_report_has_constant_fields(self):
        ep = self._ep(reg_kw=self._fake_reg())
        rpt = ep["nafdac_report"]
        assert rpt["report_type"]    == "COUNTERFEIT_PRODUCT_DETECTION"
        assert rpt["schema_version"] == "1.0"
        assert rpt["auto_flagged"]   is True

    def test_manufacturer_record_has_all_required_keys(self):
        ep = self._ep(reg_kw=self._fake_reg())
        rec = ep["manufacturer_record"]
        for key in ["brand", "scan_id", "timestamp_utc", "counterfeit_location",
                    "bypass_method", "recommendation"]:
            assert key in rec, f"manufacturer_record missing key: {key!r}"

    def test_manufacturer_recommendation_for_lookalike_chars(self):
        ep = self._ep(ocr_kw={"lookalikes": ["0 → o"]}, reg_kw=self._fake_reg())
        assert "Lookalike" in ep["manufacturer_record"]["recommendation"]

    def test_manufacturer_recommendation_for_expired_registration(self):
        ep = self._ep(reg_kw={"score": 0.1, "status": "EXPIRED",
                               "severity": "HIGH", "verified": False})
        assert "expired" in ep["manufacturer_record"]["recommendation"].lower()

    def test_manufacturer_recommendation_for_not_found(self):
        ep = self._ep(reg_kw={"score": 0.0, "status": "NOT_FOUND",
                               "severity": "CRITICAL", "verified": False})
        assert any(word in ep["manufacturer_record"]["recommendation"].lower()
                   for word in ["fabricated", "qr code", "nafdac number"])

    def test_gps_boundary_positive_extremes_locked(self):
        """lat=90, lng=180 are valid boundary coordinates."""
        ep = self._ep(reg_kw=self._fake_reg(),
                      gps={"lat": 90.0, "lng": 180.0, "accuracy": 5.0})
        assert ep["gps"]["locked"] is True

    def test_gps_boundary_negative_extremes_locked(self):
        """lat=-90, lng=-180 are valid boundary coordinates."""
        ep = self._ep(reg_kw=self._fake_reg(),
                      gps={"lat": -90.0, "lng": -180.0, "accuracy": 5.0})
        assert ep["gps"]["locked"] is True

    def test_gps_slightly_out_of_range_not_locked(self):
        ep = self._ep(reg_kw=self._fake_reg(),
                      gps={"lat": 90.001, "lng": 0.0, "accuracy": 5.0})
        assert ep["gps"]["locked"] is False

    def test_gps_missing_entirely_not_locked(self):
        """package() called with gps_coordinates=None must mark GPS as not locked."""
        clf = classify(_fuse(reg_kw=self._fake_reg()))
        ep = package(clf, gps_coordinates=None, purchase_channel="open_market")
        assert ep["gps"]["locked"] is False

    def test_score_breakdown_forwarded(self):
        ep = self._ep(reg_kw=self._fake_reg())
        for key in ["visual", "ocr", "reg"]:
            assert key in ep["score_breakdown"]

    def test_fake_enforcement_action_is_immediate_raid(self):
        ep = self._ep(reg_kw=self._fake_reg())
        assert ep["enforcement_action"] == "IMMEDIATE_RAID_CANDIDATE"

    def test_suspicious_enforcement_action_is_monitor(self):
        ep = self._ep(ocr_kw={"nafdac": None})
        assert ep["enforcement_action"] == "MONITOR_AND_LOG"


# ── GROUP G: Confidence Label Bands ───────────────────────────────────────────

class TestConfidenceLabelBands:
    """All five confidence bands and their boundary values."""

    def test_very_high_band(self):
        for score in [1.00, 0.95, 0.90]:
            assert get_confidence_label(score) == "VERY HIGH", f"score={score}"

    def test_high_band(self):
        for score in [0.89, 0.80, 0.72]:
            assert get_confidence_label(score) == "HIGH", f"score={score}"

    def test_moderate_band(self):
        for score in [0.74, 0.65, 0.55]:
            # 0.74 falls in HIGH (0.72-0.89) first; check 0.65 and 0.55
            pass
        assert get_confidence_label(0.65) == "MODERATE"
        assert get_confidence_label(0.55) == "MODERATE"

    def test_low_band(self):
        for score in [0.54, 0.45, 0.35]:
            assert get_confidence_label(score) == "LOW", f"score={score}"

    def test_very_low_band(self):
        for score in [0.34, 0.20, 0.00]:
            assert get_confidence_label(score) == "VERY LOW", f"score={score}"

    def test_score_1_point_0_is_very_high(self):
        assert get_confidence_label(1.0) == "VERY HIGH"

    def test_score_0_point_0_is_very_low(self):
        assert get_confidence_label(0.0) == "VERY LOW"


# ── GROUP H: Validate Functions ────────────────────────────────────────────────

class TestValidateFunctions:
    """Input validators for all three signal types."""

    # ── REG validate ──

    def _valid_reg(self):
        return {
            "verified": True, "verification_score": 1.0,
            "status_code": "VERIFIED", "severity": "NONE",
            "summary": "OK", "detail": "All clear.",
        }

    def test_reg_valid_passes(self):
        assert reg_validate(self._valid_reg()) == []

    def test_reg_missing_verified_caught(self):
        bad = self._valid_reg(); del bad["verified"]
        assert any("verified" in e for e in reg_validate(bad))

    def test_reg_missing_summary_caught(self):
        bad = self._valid_reg(); del bad["summary"]
        assert any("summary" in e for e in reg_validate(bad))

    def test_reg_missing_detail_caught(self):
        bad = self._valid_reg(); del bad["detail"]
        assert any("detail" in e for e in reg_validate(bad))

    def test_reg_score_above_one_caught(self):
        bad = self._valid_reg(); bad["verification_score"] = 1.5
        assert any("verification_score" in e for e in reg_validate(bad))

    def test_reg_negative_score_caught(self):
        bad = self._valid_reg(); bad["verification_score"] = -0.1
        assert any("verification_score" in e for e in reg_validate(bad))

    def test_reg_unknown_status_code_caught(self):
        bad = self._valid_reg(); bad["status_code"] = "MAYBE_FAKE"
        assert any("status_code" in e for e in reg_validate(bad))

    def test_reg_all_valid_status_codes_pass(self):
        for code in ["VERIFIED", "VERIFIED_NEAR_EXPIRY", "EXPIRED",
                     "SUBCATEGORY_MISMATCH", "NOT_FOUND", "AGENT_ERROR"]:
            reg = self._valid_reg(); reg["status_code"] = code
            assert reg_validate(reg) == [], f"{code!r} should be valid"

    def test_reg_score_exactly_zero_passes(self):
        reg = self._valid_reg(); reg["verification_score"] = 0.0
        assert reg_validate(reg) == []

    def test_reg_score_exactly_one_passes(self):
        reg = self._valid_reg(); reg["verification_score"] = 1.0
        assert reg_validate(reg) == []

    # ── OCR validate ──

    def test_ocr_valid_passes(self):
        assert ocr_validate(make_ocr()) == []

    def test_ocr_missing_metadata_caught(self):
        bad = make_ocr(); del bad["metadata"]
        assert any("metadata" in e for e in ocr_validate(bad))

    def test_ocr_missing_brand_anomaly_caught(self):
        bad = make_ocr(); del bad["brand_anomaly"]
        assert any("brand_anomaly" in e for e in ocr_validate(bad))

    def test_ocr_anomaly_score_above_one_caught(self):
        bad = make_ocr(); bad["final_text_anomaly_score"] = 1.1
        assert any("final_text_anomaly_score" in e for e in ocr_validate(bad))

    def test_ocr_negative_anomaly_score_caught(self):
        bad = make_ocr(); bad["final_text_anomaly_score"] = -0.1
        assert any("final_text_anomaly_score" in e for e in ocr_validate(bad))

    # ── Visual validate ──

    def test_visual_valid_passes_no_blocking_errors(self):
        errors = [e for e in visual_validate(make_visual())
                  if not e.startswith("WARNING")]
        assert errors == []

    def test_visual_missing_confidence_caught(self):
        bad = make_visual(); del bad["confidence"]
        assert any("confidence" in e for e in visual_validate(bad))

    def test_visual_confidence_above_one_caught(self):
        bad = make_visual(); bad["confidence"] = 1.5
        assert any("confidence" in e for e in visual_validate(bad))

    def test_visual_wrong_verdict_casing_caught(self):
        bad = make_visual(); bad["verdict"] = "authentic"  # lowercase
        assert any("verdict" in e for e in visual_validate(bad))


# ── GROUP I: RESCAN_REQUIRED Complete Path ─────────────────────────────────────

class TestRescanRequired:
    """RESCAN_REQUIRED must return a complete, structured result with no verdict scored."""

    def _rescan(self):
        return _fuse(visual_kw={"conf": 0.5, "sim": 0.6, "damage": 0.8, "blur": 3.0})

    def test_verdict_is_rescan_required(self):
        assert self._rescan()["verdict"] == "RESCAN_REQUIRED"

    def test_final_score_is_none(self):
        assert self._rescan()["final_score"] is None

    def test_weight_mode_is_rejected(self):
        assert self._rescan()["weight_mode"] == "REJECTED"

    def test_weights_used_is_none(self):
        assert self._rescan()["weights_used"] is None

    def test_override_not_applied(self):
        assert self._rescan()["override_applied"] is False

    def test_breakdown_is_empty(self):
        assert self._rescan()["breakdown"] == {}

    def test_has_rescan_required_warning(self):
        r = self._rescan()
        assert any(w["type"] == "RESCAN_REQUIRED" for w in r["warnings"])

    def test_save_for_retraining_is_true(self):
        assert self._rescan()["evidence"]["save_for_retraining"] is True

    def test_save_reason_is_unusable_extreme_blur(self):
        assert self._rescan()["evidence"]["save_reason"] == "UNUSABLE_EXTREME_BLUR"

    def test_rescan_reason_text_mentions_blur(self):
        assert "blur" in self._rescan()["rescan_reason"].lower()

    def test_blur_at_extreme_ceiling_does_not_trigger_rescan(self):
        """blur_value == EXTREME_BLUR_CEILING (5.0) is NOT a rescan (condition is <, not <=)."""
        r = _fuse(visual_kw={"conf": 0.5, "sim": 0.6,
                              "damage": 0.8, "blur": EXTREME_BLUR_CEILING})
        assert r["verdict"] != "RESCAN_REQUIRED"

    def test_blur_above_ceiling_does_not_trigger_rescan(self):
        """blur_value > 5.0 with damage=0.8 → DAMAGED mode, not RESCAN."""
        r = _fuse(visual_kw={"conf": 0.5, "sim": 0.6, "damage": 0.8, "blur": 10.0})
        assert r["verdict"] != "RESCAN_REQUIRED"

    def test_high_damage_without_extreme_blur_is_damaged_mode(self):
        """damage=0.8 but blur=20.0 → DAMAGED mode, not RESCAN."""
        r = _fuse(visual_kw={"conf": 0.5, "sim": 0.7, "damage": 0.8, "blur": 20.0})
        assert r["weight_mode"] == "DAMAGED"
        assert r["verdict"] != "RESCAN_REQUIRED"


# ── GROUP J: Full Pipeline Edge Cases ─────────────────────────────────────────

class TestFullPipelineEdgeCases:
    """end-to-end run_scan() correctness beyond what test_pipeline.py covers."""

    def test_scan_id_uuid4_format(self):
        """UUID4: 8-4-4-4-12 hex groups separated by hyphens = 36 chars total."""
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        sid = r["scan_id"]
        assert len(sid) == 36
        parts = sid.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    def test_breakdown_weighted_sum_equals_final_score(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        total = sum(r["breakdown"][s]["weighted"] for s in ["visual", "ocr", "reg"])
        assert total == pytest.approx(r["final_score"], abs=0.001)

    def test_not_found_soft_warning_in_warnings_list(self):
        r = run_scan(
            make_visual(), make_ocr(),
            make_reg(score=0.0, status="NOT_FOUND", severity="CRITICAL", verified=False),
            gps_coordinates=GPS,
        )
        types = [w["type"] for w in r["warnings"]]
        assert "NOT_FOUND" in types

    def test_subcategory_mismatch_soft_warning_in_warnings_list(self):
        r = run_scan(
            make_visual(), make_ocr(),
            make_reg(score=0.2, status="SUBCATEGORY_MISMATCH",
                     severity="CRITICAL", verified=False),
            gps_coordinates=GPS,
        )
        types = [w["type"] for w in r["warnings"]]
        assert "SUBCATEGORY_MISMATCH" in types

    def test_authentic_does_not_generate_evidence_package(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        assert r["evidence_package"] is None

    def test_suspicious_generates_evidence_package(self):
        r = run_scan(make_visual(), make_ocr(nafdac=None), make_reg(), gps_coordinates=GPS)
        assert r["evidence_package"] is not None

    def test_fake_always_generates_evidence_package(self):
        r = run_scan(
            make_visual(), make_ocr(),
            make_reg(score=0.0, status="AGENT_ERROR", severity="CRITICAL", verified=False),
            gps_coordinates=GPS,
        )
        assert r["evidence_package"] is not None

    def test_all_expected_keys_present_in_authentic_result(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        expected_keys = [
            "status", "scan_id", "verdict", "action", "final_score",
            "severity", "report_priority", "simple_instruction",
            "atlas_instruction", "override_applied", "override_summary",
            "warnings", "breakdown", "weight_mode", "evidence_package",
            "errors", "timestamp",
        ]
        for key in expected_keys:
            assert key in r, f"Missing key in run_scan result: {key!r}"

    def test_override_applied_false_clean_scan(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        assert r["override_applied"] is False

    def test_override_summary_none_for_clean_scan(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        assert r["override_summary"] is None

    def test_errors_list_empty_for_all_signals_present(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        assert r["errors"] == []

    def test_near_expiry_never_produces_fake(self):
        r = run_scan(
            make_visual(), make_ocr(),
            make_reg(score=0.85, status="VERIFIED_NEAR_EXPIRY",
                     severity="WARNING", verified=True, near_expiry=True, days=15),
            gps_coordinates=GPS,
        )
        assert r["verdict"] != "FAKE"

    def test_timestamp_is_iso8601(self):
        r = run_scan(make_visual(), make_ocr(), make_reg(), gps_coordinates=GPS)
        assert "T" in r["timestamp"]   # ISO 8601: "2025-01-01T12:00:00+00:00"
        assert r["timestamp"].endswith("+00:00") or r["timestamp"].endswith("Z") or "UTC" in str(r["timestamp"])
