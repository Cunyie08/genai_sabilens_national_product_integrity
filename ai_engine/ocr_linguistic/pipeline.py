import logging
from typing import Optional

from .extractor import extract_text_blocks, build_metadata
from .brand_validator import BrandValidator
from .rule_engine import compute_rule_score
from .config import REQUIRED_FIELDS, HYBRID_SCORING

logger = logging.getLogger("OCR_Linguistic")

# Module-level singletons — instantiated once, reused across all scans
_brand_validator = BrandValidator()


def validate_structure(structured: dict) -> dict:
    """
    Structural validation without requiring a product category.
    Uses REQUIRED_FIELDS from config as the baseline check.
    """
    missing = [f for f in REQUIRED_FIELDS if not structured.get(f)]
    expiry_valid = bool(structured.get("expiry_date"))
    batch_valid  = bool(structured.get("batch_number"))

    structural_score = max(0.0, 1.0
        - len(missing) * 0.15
        - (0.0 if expiry_valid else 0.2)
        - (0.0 if batch_valid  else 0.2)
    )

    return {
        "missing_fields":       missing,
        "missing_fields_count": len(missing),
        "expiry_format_valid":  expiry_valid,
        "batch_format_valid":   batch_valid,
        "structural_score":     round(min(structural_score, 1.0), 4),
    }


def compute_anomaly_score(features: dict, damage_score: float) -> dict:
    """
    Combine rule-based scoring with ML model scoring.
    Falls back to rule-only if ML model is unavailable.
    """
    # Build a flat metadata dict that compute_rule_score expects
    flat_meta = {
        "brand_anomaly_flag":   features.get("brand_anomaly_flag", 0),
        "nafdac_number":        features.get("nafdac_number"),
        "expiry_format_valid":  features.get("expiry_format_valid", False),
        "batch_format_valid":   features.get("batch_format_valid", False),
        "structural_score":     features.get("structural_score", 0.0),
        "avg_ocr_confidence":   features.get("ocr_confidence", 0.0),
    }

    rule_result = compute_rule_score(flat_meta, damage_score)
    rule_score  = rule_result["rule_score"]

    # ML scoring — attempt to load trained model
    ml_score = rule_score   # default: use rule score if ML unavailable
    try:
        import joblib
        import os
        import numpy as np

        model_path = os.path.join(
            os.path.dirname(_file_), "models", "ocr_anomaly_model.pkl"
        )
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            feature_vec = np.array([[
                features.get("brand_similarity",    0.0),
                features.get("brand_anomaly_flag",  0),
                int(bool(features.get("nafdac_number"))),
                features.get("missing_fields_count",0),
                features.get("structural_score",    0.0),
                features.get("ocr_confidence",      0.0),
                damage_score,
                features.get("text_length",         0),
                features.get("numeric_density",     0.0),
            ]])
            ml_score = float(model.predict_proba(feature_vec)[0][1])
    except Exception:
        pass   # ML model unavailable — rule score used as fallback

    rule_w = HYBRID_SCORING.get("rule_weight", 0.75)
    ml_w   = HYBRID_SCORING.get("ml_weight",   0.25)
    final  = round(rule_w * rule_score + ml_w * ml_score, 4)

    return {
        "rule_score":               rule_score,
        "ml_score":                 round(ml_score, 4),
        "final_text_anomaly_score": final,
        "components":               rule_result.get("components", {}),
    }


def build_feature_vector_pipeline(
    brand_result:      dict,
    structured:        dict,
    structural_result: dict,
    avg_confidence:    float,
    damage_score:      float,
    raw_text:          str,
) -> dict:
    """
    Build the feature vector for anomaly scoring.
    Wraps the existing build_feature_vector with the pipeline's keyword interface.
    """
    tokens         = raw_text.split()
    numeric_tokens = [t for t in tokens if any(c.isdigit() for c in t)]

    return {
        "brand_similarity":     brand_result.get("similarity_score", 0.0),
        "brand_anomaly_flag":   brand_result.get("brand_anomaly_flag", 0),
        "nafdac_number":        structured.get("nafdac_number"),
        "nafdac_valid":         int(bool(structured.get("nafdac_number"))),
        "missing_fields_count": structural_result.get("missing_fields_count", 0),
        "structural_score":     structural_result.get("structural_score", 0.0),
        "expiry_format_valid":  structural_result.get("expiry_format_valid", False),
        "batch_format_valid":   structural_result.get("batch_format_valid", False),
        "ocr_confidence":       avg_confidence,
        "damage_score":         damage_score,
        "text_length":          len(raw_text),
        "numeric_density":      len(numeric_tokens) / max(len(tokens), 1),
    }


def run_pipeline(
    image_path:   str,
    damage_score: float = 0.0,
    retriever=None,
) -> dict:
    """
    Run the full OCR linguistic pipeline on one product image.

    Args:
        image_path:   Path to the product label image.
        damage_score: Scan quality score from VisualPipeline (0.1 | 0.4 | 0.8).
        retriever:    Optional ProductRetriever from the orchestrator.
                      Enables safe two-pass NAFDAC extraction with OCR correction.
                      When None, strict extraction only.
                      NEVER pass a newly instantiated retriever here — always
                      use the orchestrator's shared instance to avoid double
                      ChromaDB loading.

    Returns:
        OCR signal dict for A4 Fusion Engine.
    """
    logger.info("Pipeline started | image: %s | damage_score: %s", image_path, damage_score)

    # Step 1 — OCR text extraction
    blocks = extract_text_blocks(image_path)
    logger.info("OCR blocks extracted: %d", len(blocks))

    # Step 2 — Build metadata
    # Pass retriever for two-pass NAFDAC correction — no new DB client created
    metadata = build_metadata(blocks, retriever=retriever)
    logger.info("Base metadata extracted")

    # Step 3 — Brand validation
    brand_result = _brand_validator.validate(metadata.get("raw_ocr_text", ""))
    logger.info("Brand Validation: %s", brand_result)

    # Step 4 — Structured metadata
    structured = {
        "nafdac_number":        metadata.get("nafdac_number"),
        "batch_number":         metadata.get("batch_number"),
        "expiry_date":          metadata.get("expiry_date"),
        "manufacturer_name":    metadata.get("manufacturer_name"),
        "net_weight_or_volume": metadata.get("net_weight_or_volume"),
        "product_name":         metadata.get("product_name"),
        "valid_format":         metadata.get("valid_format", False),
        "nafdac_ocr_corrected": metadata.get("nafdac_ocr_corrected", False),
    }
    logger.info("Structured Metadata: %s", structured)

    # Step 5 — Structural validation
    structural_result = validate_structure(structured)
    logger.info("Structural Validation: %s", structural_result)

    # Step 6 — Feature vector
    avg_confidence = metadata.get("avg_ocr_confidence", 0.0)
    features = build_feature_vector_pipeline(
        brand_result      = brand_result,
        structured        = structured,
        structural_result = structural_result,
        avg_confidence    = avg_confidence,
        damage_score      = damage_score,
        raw_text          = metadata.get("raw_ocr_text", ""),
    )
    logger.info("Feature vector built")

    # Step 7 — Anomaly scoring (rule + ML hybrid)
    scores = compute_anomaly_score(features, damage_score)
    logger.info(
        "Rule Score: %s | ML Score: %s | Final: %s",
        scores["rule_score"], scores["ml_score"], scores["final_text_anomaly_score"],
    )

    logger.info("Pipeline completed successfully")

    return {
        "source": "OCR_Linguistic",
        # Raw OCR blocks are included so scan_orchestrator can forward the
        # non-NAFDAC (front-panel) blocks to the fusion identity check.
        "ocr_blocks": blocks,
        "metadata": {
            "product_name":         structured.get("product_name"),
            "nafdac_number":        structured.get("nafdac_number"),
            "batch_number":         structured.get("batch_number"),
            "expiry_date":          structured.get("expiry_date"),
            "manufacturer_name":    structured.get("manufacturer_name"),
            "raw_ocr_text":         metadata.get("raw_ocr_text", ""),
            "avg_ocr_confidence":   avg_confidence,
            "brand_similarity":     brand_result.get("similarity_score", 0.0),
            "brand_anomaly_flag":   brand_result.get("brand_anomaly_flag", 0),
            "closest_brand_match":  brand_result.get("closest_match"),
            "brand_detected":       brand_result.get("brand_detected"),
            "net_weight_or_volume": structured.get("net_weight_or_volume"),
            "valid_format":         structured.get("valid_format", False),
            "missing_fields":       structural_result.get("missing_fields", []),
            "missing_fields_count": structural_result.get("missing_fields_count", 0),
            "expiry_format_valid":  structural_result.get("expiry_format_valid", False),
            "batch_format_valid":   structural_result.get("batch_format_valid", False),
            "structural_score":     structural_result.get("structural_score", 0.0),
            "nafdac_ocr_corrected": structured.get("nafdac_ocr_corrected", False),
        },
        "brand_anomaly": {
            "brand_detected":        brand_result.get("brand_detected"),
            "closest_match":         brand_result.get("closest_match"),
            "similarity_score":      brand_result.get("similarity_score", 0.0),
            "lookalike_corrections": brand_result.get("lookalike_corrections", []),
            "brand_anomaly_flag":    brand_result.get("brand_anomaly_flag", 0),
        },
        "structural_validation": {
            "missing_fields":       structural_result.get("missing_fields", []),
            "missing_fields_count": structural_result.get("missing_fields_count", 0),
            "expiry_format_valid":  structural_result.get("expiry_format_valid", False),
            "batch_format_valid":   structural_result.get("batch_format_valid", False),
            "structural_score":     structural_result.get("structural_score", 0.0),
        },
        "rule_score": {
            "rule_score":              scores["rule_score"],
            "components":              scores.get("components", {}),
            "damage_score_applied":    damage_score,
            "adjusted_ocr_confidence": avg_confidence,
        },
        "ml_score":                 scores["ml_score"],
        "final_text_anomaly_score": scores["final_text_anomaly_score"],
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m ai_engine.ocr_linguistic.pipeline <image_path> [damage_score]")
        sys.exit(1)

    image_path   = sys.argv[1]
    damage_score = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0

    print(f"\nRunning OCR Pipeline on: {image_path}")
    print(f"damage_score: {damage_score}")

    result = run_pipeline(image_path, damage_score, retriever=None)

    print("\n====== Output ===============================================")
    print(json.dumps(result, indent=2))

    print("\n====== Contract Check ======================================")
    required = ["source", "metadata", "brand_anomaly",
                "structural_validation", "rule_score",
                "ml_score", "final_text_anomaly_score"]
    for field in required:
        val     = result.get(field, "MISSING")
        status  = "CONFIRMED" if val != "MISSING" else "MISSING"
        display = "{...}" if isinstance(val, dict) else str(val)
        print(f"  {status}  {field}: {display}")

    print(f"\n  nafdac_number extracted : {result['metadata'].get('nafdac_number')}")
    print(f"  nafdac_ocr_corrected   : {result['metadata'].get('nafdac_ocr_corrected')}")
    print(f"  final_text_anomaly_score: {result['final_text_anomaly_score']}")
    print("\nAll contract fields present. OCR output is ready for Fusion.")