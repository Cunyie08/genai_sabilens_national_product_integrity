"""
visual_pipeline.py  –  SabiLens Visual Module v2
==================================================
WHAT CHANGED FROM v1 AND WHY
------------------------------
v1 CONFIDENCE FORMULA:
    confidence = raw_similarity × (1 − damage_score)
 
This is the ROOT CAUSE of the fake-passes-as-authentic bug.
 
If raw_similarity = 0.88 (ResNet50 fooled by a visually close fake)
and damage_score  = 0.1  (sharp image, no blur)
Then confidence   = 0.88 × 0.9 = 0.792 → "Authentic" ✗
 
The formula has NO mechanism to reject a fake that LOOKS similar.
 
v2 CONFIDENCE FORMULA:
    confidence = weighted_similarity × quality_factor × penalty_factor
 
Where:
  weighted_similarity = from SimilarityEngine v2 (front-weighted, EfficientNet)
  quality_factor      = 1 − damage_score  (unchanged from v1)
  penalty_factor      = product of all active penalty multipliers:
      × 0.55  if anomaly_flag   (similarity < 0.60 → very suspicious)
      × 0.70  if ambiguity_flag (margin to 2nd product < 0.08 → unclear match)
 
VETO RULES (hard rules that override the score entirely):
  → confidence set to 0.10 ("Fake") if:
      • similarity < 0.40        (too low to be genuine)
      • anomaly_flag AND ambiguity_flag simultaneously
      • no_product_detected
 
VERDICT THRESHOLDS (tightened from v1):
  ≥ 0.72  → Authentic    (was 0.75 in v1, but penalty system means genuine
                           authentic products still comfortably clear this)
  ≥ 0.45  → Suspicious
  <  0.45 → Fake
 
OUTPUT CONTRACT (superset of v1 – all v1 fields present + new fields):
  {
      "product":           str,    # matched product name
      "Visual Similarity": float,  # weighted cosine similarity (v2 engine)
      "margin":            float,  # gap to 2nd-best product
      "anomaly_flag":      bool,   # similarity too low
      "ambiguity_flag":    bool,   # match too close to another product
      "damage_score":      float,  # 0.1 | 0.4 | 0.8
      "blur_value":        float,  # raw Laplacian for Fusion scan triage
      "penalty_applied":   float,  # total penalty multiplier (1.0 = none)
      "confidence":        float,  # final adjusted score 0.0–1.0
      "verdict":           str,    # "Authentic" | "Suspicious" | "Fake"
      "flags":             list,   # human-readable list of active warnings
  }
"""
 
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
 
import json
 
from vision_engine.similarity.similarity_engine     import SimilarityEngine
from vision_engine.damage_detection.damage_detector import DamageDetector
from vision_engine.regions.yolo_detector            import RegionDetector
 
# ── Verdict thresholds ────────────────────────────────────────────────────────
AUTHENTIC_THRESHOLD  = 0.65
SUSPICIOUS_THRESHOLD = 0.45
 
# ── Veto thresholds ───────────────────────────────────────────────────────────
HARD_FAKE_SIMILARITY = 0.40   # below this = automatically Fake regardless
 
# ── Penalty multipliers ───────────────────────────────────────────────────────
ANOMALY_PENALTY   = 0.55   # applied when similarity < ANOMALY_THRESHOLD
AMBIGUITY_PENALTY = 0.70   # applied when margin to 2nd product is small
 
 
class VisualPipeline:
 
    def __init__(self):
        _BASE = os.path.dirname(os.path.abspath(__file__))
        self.sim_engine      = SimilarityEngine(
            os.path.join(_BASE, "..", "embeddings", "reference_embeddings.pkl")
        )
        self.region_detector = RegionDetector()
        self.damage_detector = DamageDetector()
 
    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────
 
    def analyze(self, image_path: str) -> dict:
        """
        Run the full v2 visual analysis pipeline on one product image.
 
        Args:
            image_path: File path to the product image.
 
        Returns:
            Dict matching the v2 output contract.
        """
        flags = []
 
        # ── 1. Region detection (YOLO, falls back to full image) ──────────
        regions    = self.region_detector.detect_regions(image_path)
        logo_input = regions.get("brand_logo", image_path)
 
        # ── 2. Similarity comparison (v2 engine) ──────────────────────────
        sim_result     = self.sim_engine.compare(logo_input)
        raw_similarity = sim_result["similarity"]
        margin         = sim_result["margin"]
        anomaly_flag   = sim_result["anomaly_flag"]
        ambiguity_flag = sim_result["ambiguity_flag"]
        product        = sim_result["product"]
 
        # ── 3. Scan quality ───────────────────────────────────────────────
        damage_result = self.damage_detector.damage_score(image_path)
        damage_score  = damage_result["damage_score"]
        blur_value    = damage_result["blur_value"]
 
        # ── 4. Hard veto checks ───────────────────────────────────────────
        if product == "NO_PRODUCT_DETECTED":
            flags.append("NO_PRODUCT_DETECTED")
            return self._build_result(
                product, raw_similarity, margin,
                anomaly_flag, ambiguity_flag,
                damage_score, blur_value,
                penalty=1.0, confidence=0.05,
                verdict="Fake", flags=flags,
            )
 
        if raw_similarity < HARD_FAKE_SIMILARITY:
            flags.append(f"SIMILARITY_TOO_LOW ({raw_similarity:.3f} < {HARD_FAKE_SIMILARITY})")
            return self._build_result(
                product, raw_similarity, margin,
                anomaly_flag, ambiguity_flag,
                damage_score, blur_value,
                penalty=1.0, confidence=0.10,
                verdict="Fake", flags=flags,
            )
 
        if anomaly_flag and ambiguity_flag:
            flags.append("DUAL_FLAG_VETO: anomaly + ambiguity both active")
            return self._build_result(
                product, raw_similarity, margin,
                anomaly_flag, ambiguity_flag,
                damage_score, blur_value,
                penalty=1.0, confidence=0.12,
                verdict="Fake", flags=flags,
            )
 
        # ── 5. Penalty calculation ─────────────────────────────────────────
        penalty = 1.0
 
        if blur_value > 200 and damage_score <= 0.1:
            penalty *= 0.70
            flags.append(f"BLUR_ANOMALY ({0.70}×): blur_value={blur_value:.1f} suggests composited/altered image")
 
        if anomaly_flag:
            penalty *= ANOMALY_PENALTY
            flags.append(f"ANOMALY_PENALTY ({ANOMALY_PENALTY}×): similarity below threshold")
 
        if ambiguity_flag:
            penalty *= AMBIGUITY_PENALTY
            flags.append(f"AMBIGUITY_PENALTY ({AMBIGUITY_PENALTY}×): weak margin to 2nd product ({margin:.3f})")
 
        # ── 6. Quality factor (unchanged from v1) ─────────────────────────
        quality_factor = 1.0 - damage_score
        if damage_score >= 0.4:
            flags.append(f"SCAN_QUALITY_WARNING: blur_value={blur_value:.1f}, damage_score={damage_score}")
 
        # ── 7. Final confidence ───────────────────────────────────────────
        confidence = raw_similarity * quality_factor * penalty
        confidence = round(min(max(confidence, 0.0), 1.0), 4)
 
        # ── 8. Verdict ────────────────────────────────────────────────────
        verdict = self._classify(confidence)
 
        return self._build_result(
            product, raw_similarity, margin,
            anomaly_flag, ambiguity_flag,
            damage_score, blur_value,
            penalty=round(penalty, 4),
            confidence=confidence,
            verdict=verdict,
            flags=flags,
        )
 
    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────
 
    @staticmethod
    def _classify(confidence: float) -> str:
        if confidence >= AUTHENTIC_THRESHOLD:
            return "Authentic"
        elif confidence >= SUSPICIOUS_THRESHOLD:
            return "Suspicious"
        else:
            return "Fake"
 
    @staticmethod
    def _build_result(
        product, raw_similarity, margin,
        anomaly_flag, ambiguity_flag,
        damage_score, blur_value,
        penalty, confidence, verdict, flags,
    ) -> dict:
        return {
            "product":           product,
            "Visual Similarity": raw_similarity,
            "margin":            margin,
            "anomaly_flag":      anomaly_flag,
            "ambiguity_flag":    ambiguity_flag,
            "damage_score":      damage_score,
            "blur_value":        blur_value,
            "penalty_applied":   penalty,
            "confidence":        confidence,
            "verdict":           verdict,
            "flags":             flags,
        }
 
 
# ── CLI entry point (unchanged from v1) ───────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visual_pipeline.py path/to/image.jpg")
        sys.exit(1)
 
    image_path = sys.argv[1]
    print(f"\nRunning VisualPipeline v2 on: {image_path}\n")
 
    pipeline = VisualPipeline()
    result   = pipeline.analyze(image_path)
 
    print("===== Output ============================================")
    print(json.dumps(result, indent=2))
 
    print("\n===== Contract Check ====================================")
    required = [
        "product", "Visual Similarity", "margin",
        "anomaly_flag", "ambiguity_flag",
        "damage_score", "blur_value",
        "penalty_applied", "confidence", "verdict", "flags",
    ]
    all_ok = True
    for field in required:
        val    = result.get(field, "MISSING")
        status = "✓" if val != "MISSING" else "✗ MISSING"
        if val == "MISSING":
            all_ok = False
        print(f"  {status}  {field}: {val}")
 
    print()
    if all_ok:
        print("All contract fields present. Visual v2 output is ready for Fusion.")
    else:
        print("Missing fields detected. Check pipeline output.")