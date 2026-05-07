"""
Coordinates Vision, OCR, Regulatory, and Fusion
for every product label scan in SabiLens.

Backend creates one ScanOrchestrator instance at startup and calls scan() per request.

RESPONSIBILITY OF THIS FILE:
  Collect signals from Visual, OCR, Regulatory and hand them to Fusion.
  That is all.

SINGLE CHROMADB INSTANCE:
  The regulatory agent owns the only ChromaDB client and ProductRetriever.
  The OCR pipeline receives the retriever as an argument for two-pass NAFDAC
  correction. It never creates its own ChromaDB client.
  This prevents double-loading when OCR and Regulatory run in parallel threads.

CATEGORY FALLBACK CHAIN (when frontend sends category="unknown"):
  0. DB lookup via category_resolver callable (backend-injected, DB-agnostic).
  1. Frontend scanned_category if it maps to a known NAFDAC category.
  2. OCR-detected brand name (e.g. "Vaseline" -> "Cosmetics").
  3. Visual product match (e.g. "vaseline_intensive_care" -> "Cosmetics").
  4. Pass "unknown" to regulatory - agent uses semantic search (soft warn only).
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from ai_engine.agent.verification_agent import NAFDACVerificationAgent
from ai_engine.fusion_engine.main import run_scan
from ai_engine.orchestrator.pipeline import (
    AgentSignal,
    PipelineResult,
    MOCK_CONFIDENCE,
)

logger = logging.getLogger("ScanOrchestrator")


# NAFDAC Category Map 

NAFDAC_CATEGORY_MAP: dict = {
    "corn flakes":                      "Cereals and Cereal Products",
    "cornflakes":                       "Cereals and Cereal Products",
    "coco pops":                        "Cereals and Cereal Products",
    "go grains":                        "Cereals and Cereal Products",
    "pasta":                            "Cereal Products",
    "spaghetti":                        "Cereal Products",
    "noodles":                          "Cereal Products",
    "vegetable oil":                    "Edible Oils and Fats",
    "soya oil":                         "Edible Oils and Fats",
    "cooking oil":                      "Edible Oils and Fats",
    "sugar":                            "Food Additives",
    "tomato paste":                     "Preserved Fruits and Vegetables",
    "tomato":                           "Preserved Fruits and Vegetables",
    "chicken seasoning":                "Condiments/Spices/Seasonings",
    "seasoning":                        "Condiments/Spices/Seasonings",
    "spice":                            "Condiments/Spices/Seasonings",
    "tea":                              "Non-Alcoholic Beverages",
    "lipton":                           "Non-Alcoholic Beverages",
    "juice":                            "Non-Alcoholic Beverages",
    "water":                            "Non-Alcoholic Beverages",
    "body spray":                       "Cosmetics",
    "antiperspirant":                   "Cosmetics",
    "deodorant":                        "Cosmetics",
    "toothpaste":                       "Cosmetics",
    "toilet roll":                      "Cosmetics",
    "tissue":                           "Cosmetics",
    "vaseline":                         "Cosmetics",
    "petroleum jelly":                  "Cosmetics",
    "lotion":                           "Cosmetics",
    "cream":                            "Cosmetics",
    "soap":                             "Cosmetics",
    "gel":                              "Cosmetics",
    "kellogg":                          "Cereals and Cereal Products",
    "indomie":                          "Cereal Products",
    "golden terra":                     "Edible Oils and Fats",
    "unilever":                         "Cosmetics",
    # Visual pipeline product match names
    "vaseline_intensive_care":          "Cosmetics",
    "vaseline_eventone_b3_lotion":      "Cosmetics",
    "vaseline_blueseal":                "Cosmetics",
    "axe_bodyspray":                    "Cosmetics",
    "dove_cream_bar":                   "Cosmetics",
    "dove_coconut_jasmine":             "Cosmetics",
    "dove_pear_aloevera":               "Cosmetics",
    "closeup_complete_fresh":           "Cosmetics",
    "pepsodent":                        "Cosmetics",
    "familia_2_toilet_rolls":           "Cosmetics",
    "rexona_antiperspirant_gel":        "Cosmetics",
    "kelloggs_cornflakes":              "Cereals and Cereal Products",
    "kelloggs_coco_pops":               "Cereals and Cereal Products",
    "kelloggs_go_grains":               "Cereals and Cereal Products",
    "golden_penny_pasta_spaghettini":   "Cereal Products",
    "indomie_chicken_flavor":           "Cereal Products",
    "golden_terra_soya_oil":            "Edible Oils and Fats",
    "sedoso_vegetable_oil":             "Edible Oils and Fats",
    "dangote_sugar_refined":            "Food Additives",
    "peppe_terra_cooking_tomato_paste": "Preserved Fruits and Vegetables",
    "terra_chicken_seasoning":          "Condiments/Spices/Seasonings",
    "lipton_yellow_label_tea":          "Non-Alcoholic Beverages",
}


def _map_to_nafdac_category(scanned_category: str) -> str:
    if not scanned_category or scanned_category.strip().lower() in ("", "unknown"):
        return "unknown"
    lower = scanned_category.lower().strip()
    for keyword, nafdac_cat in NAFDAC_CATEGORY_MAP.items():
        if keyword in lower:
            return nafdac_cat
    return scanned_category


def _resolve_category(
    scanned_category: str,
    ocr_signal:       AgentSignal,
    vision_signal:    AgentSignal = None,
) -> str:
    # Step 1: frontend category
    mapped = _map_to_nafdac_category(scanned_category)
    if mapped and mapped.lower() != "unknown":
        return mapped

    # Step 2: OCR brand
    brand = (
        ocr_signal.payload.get("brand_anomaly", {}).get("brand_detected")
        or ocr_signal.payload.get("metadata", {}).get("brand_detected")
    )
    if brand:
        brand_mapped = _map_to_nafdac_category(brand)
        if brand_mapped.lower() != brand.lower():
            logger.info("Category resolved from OCR brand: '%s' -> '%s'", brand, brand_mapped)
            return brand_mapped
        logger.info("Category fallback: using raw OCR brand '%s'.", brand)
        return brand

    # Step 3: A1 visual product match
    if vision_signal and not vision_signal.mocked:
        product_matched = vision_signal.payload.get("product", "")
        if product_matched:
            vision_mapped = _map_to_nafdac_category(product_matched)
            if vision_mapped.lower() != product_matched.lower():
                logger.info(
                    "Category resolved from visual match: '%s' -> '%s'",
                    product_matched, vision_mapped,
                )
                return vision_mapped

    logger.warning("Category unresolved. Passing 'unknown' to regulatory.")
    return "unknown"


class ScanOrchestrator:
    """
    Collects signals from visual, OCR, regulatory and hands them to fusion.

    KEY DESIGN: Only one ChromaDB instance exists in the entire pipeline.
    It is owned by the regulatory agent and shared with OCR via self._retriever.
    """

    def __init__(self):
        logger.info("Initialising ScanOrchestrator - loading REG agent and Visual pipeline...")

        self._regulatory_agent = NAFDACVerificationAgent()

        # Share the retriever from the regulatory agent with OCR.
        # This is the ONLY ProductRetriever / ChromaDB client in the pipeline.
        self._retriever = getattr(self._regulatory_agent, 'retriever', None)
        if self._retriever:
            logger.info("ProductRetriever shared from regulatory agent.")
        else:
            logger.warning(
                "Could not access ProductRetriever from regulatory agent. "
                "Two-pass NAFDAC OCR correction disabled (strict extraction only)."
            )

        # Pre-load VisualPipeline at startup
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'visual'))
            from vision_engine.pipeline.visual_pipeline import VisualPipeline as _VP
            self._visual_pipeline = _VP()
            logger.info("VisualPipeline pre-loaded at startup.")
        except Exception as _exc:
            logger.error(
                "VisualPipeline pre-load FAILED — %s: %s. "
                "Vision signals will be MOCKED. "
                "Ensure torch, torchvision, ultralytics are installed on this host.",
                type(_exc).__name__, _exc,
            )
            self._visual_pipeline = None

        logger.info("ScanOrchestrator ready.")

    def scan(
        self,
        image_path:        str,
        nafdac_no:         str,
        scanned_category:  str,
        gps_coordinates:   dict,
        purchase_channel:  str,
        image_paths:       Optional[list] = None,
        receipt_image:     Optional[str]  = None,
        storefront_image:  Optional[str]  = None,
        damage_score:      float = 0.0,
        category_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ) -> PipelineResult:

        all_image_paths = list(image_paths) if image_paths else [image_path]
        all_image_paths = [p for p in all_image_paths if p and p != "EXPLAIN_MODE_NO_IMAGE"]
        if not all_image_paths:
            all_image_paths = [image_path]

        logger.info(
            "scan() | nafdac_no=%s | category=%s | channel=%s | images=%d | primary=%s",
            nafdac_no, scanned_category, purchase_channel, len(all_image_paths), image_path,
        )

        _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scan-worker")

        # Pass shared retriever to OCR - no new ChromaDB instance created
        ocr_future    = _pool.submit(
            self._run_ocr_multi, all_image_paths, damage_score, self._retriever
        )
        vision_future = _pool.submit(self._run_vision_multi, all_image_paths)

        ocr_signal = ocr_future.result()

        effective_nafdac = nafdac_no or (
            ocr_signal.payload.get("metadata", {}).get("nafdac_number") or ""
        )

        # DB category lookup (highest priority)
        if category_resolver and effective_nafdac:
            try:
                db_category = category_resolver(effective_nafdac)
                if db_category:
                    logger.info(
                        "Category from DB | nafdac='%s' -> '%s'",
                        effective_nafdac, db_category,
                    )
                    scanned_category = db_category
            except Exception:
                logger.warning("category_resolver failed.", exc_info=True)

        # Collect vision before category resolution so A1 match available
        vision_signal = vision_future.result()

        # Short-circuit — if no product detected, skip OCR, regulatory, and fusion
        if vision_signal.payload.get("no_product_detected"):
            logger.info("scan() | NO_PRODUCT_DETECTED - skipping OCR, regulatory, fusion")
            _pool.shutdown(wait=False)
            # Return a minimal PipelineResult with INVALID_IMAGE verdict
            mock_ocr = self._mock_ocr_signal()
            mock_reg = AgentSignal(
                agent_id="regulatory", available=False, confidence=0.0, mocked=True,
                payload={"status_code": "SKIPPED", "verified": False,
                         "verification_score": 0.0, "severity": "NONE",
                         "summary": "", "detail": "", "fallback_used": False,
                         "tools_called": [], "reasoning_trace": [],
                         "expiry_check": None, "alignment": None,
                         "matched_record": None, "all_records": []}
            )
            fusion_signal = self._run_fusion(
                vision_signal     = vision_signal,
                ocr_signal        = mock_ocr,
                regulatory_signal = mock_reg,
                gps_coordinates   = gps_coordinates,
                purchase_channel  = purchase_channel,
                receipt_image     = receipt_image,
                storefront_image  = storefront_image,
            )
            fusion = fusion_signal.payload
            return PipelineResult(
                vision_signal      = vision_signal,
                ocr_signal         = mock_ocr,
                regulatory_signal  = mock_reg,
                fusion_signal      = fusion_signal,
                status             = "INVALID_IMAGE",
                scan_id            = fusion.get("scan_id", ""),
                final_verdict      = "INVALID_IMAGE",
                final_score        = 0.0,
                final_severity     = "NONE",
                action             = "INVALID IMAGE",
                simple_instruction = "No product detected. Please take a clear photo of the product label and try again.",
                atlas_instruction  = "",
                summary            = "Image does not contain a recognisable product label.",
                detail             = "",
                report_priority    = "NONE",
                override_applied   = True,
                override_summary   = "NO_PRODUCT_DETECTED",
                warnings           = [{"type": "NO_PRODUCT_DETECTED", "message": "Image does not contain a recognisable product label."}],
                breakdown          = {},
                evidence_package   = {},
                rescan_required    = False,
                signals_used       = [],
            )

        nafdac_category = _resolve_category(scanned_category, ocr_signal, vision_signal)
        logger.info(
            "Category resolved | frontend='%s' -> regulatory='%s'",
            scanned_category, nafdac_category,
        )

        reg_future        = _pool.submit(self._run_regulatory, effective_nafdac, nafdac_category)
        regulatory_signal = reg_future.result()
        _pool.shutdown(wait=False)

        fusion_signal = self._run_fusion(
            vision_signal     = vision_signal,
            ocr_signal        = ocr_signal,
            regulatory_signal = regulatory_signal,
            gps_coordinates   = gps_coordinates,
            purchase_channel  = purchase_channel,
            receipt_image     = receipt_image,
            storefront_image  = storefront_image,
        )

        fusion = fusion_signal.payload

        return PipelineResult(
            vision_signal      = vision_signal,
            ocr_signal         = ocr_signal,
            regulatory_signal  = regulatory_signal,
            fusion_signal      = fusion_signal,
            status             = fusion.get("status",             "FAILSAFE"),
            scan_id            = fusion.get("scan_id",            ""),
            final_verdict      = fusion.get("verdict",            "FAKE"),
            final_score        = fusion.get("final_score",        0.0),
            final_severity     = fusion.get("severity",           "CRITICAL"),
            action             = fusion.get("action",             "DO NOT BUY"),
            simple_instruction = fusion.get("simple_instruction", ""),
            atlas_instruction  = fusion.get("atlas_instruction",  ""),
            summary            = fusion.get("atlas_summary",      ""),
            detail             = fusion.get("atlas_detail",       ""),
            report_priority    = fusion.get("report_priority",    "NONE"),
            override_applied   = fusion.get("override_applied",   False),
            override_summary   = fusion.get("override_summary",   ""),
            warnings           = fusion.get("warnings",           []),
            breakdown          = fusion.get("breakdown",          {}),
            evidence_package   = fusion.get("evidence_package",   {}),
            rescan_required    = fusion.get("status") == "RESCAN_REQUIRED",
            signals_used       = [
                agent for agent in ["visual", "ocr", "reg"]
                if fusion.get("breakdown", {}).get(agent, {}).get("weight", 0) > 0
            ],
        )

    def _run_ocr_multi(self, image_paths: list, damage_score: float, retriever=None) -> AgentSignal:
        try:
            from ocr_linguistic.pipeline import run_pipeline as ocr_run_pipeline
        except Exception as _exc:
            logger.error(
                "OCR import FAILED — %s: %s. "
                "OCR signals will be MOCKED. "
                "Ensure paddlepaddle and paddleocr are installed on this host.",
                type(_exc).__name__, _exc,
            )
            return self._mock_ocr_signal()

        results = []
        for path in image_paths:
            try:
                logger.info("OCR | image=%s | damage_score=%s", path, damage_score)
                r = ocr_run_pipeline(path, damage_score, retriever=retriever)
                results.append(r)
                logger.info(
                    "OCR image done | nafdac=%s | anomaly=%.3f",
                    r.get("metadata", {}).get("nafdac_number"),
                    r.get("final_text_anomaly_score", 0.5),
                )
            except Exception:
                logger.warning("OCR failed for %s.", path, exc_info=True)

        if not results:
            return self._mock_ocr_signal()
        



        def _score(r):
            has_nafdac = 1 if r.get("metadata", {}).get("nafdac_number") else 0
            return (has_nafdac, -r.get("final_text_anomaly_score", 0.5))

        best = max(results, key=_score)
        logger.info(
            "OCR multi complete | %d images | best nafdac=%s | anomaly=%.3f",
            len(results),
            best.get("metadata", {}).get("nafdac_number"),
            best.get("final_text_anomaly_score", 0.5),
        )
        return AgentSignal(
            agent_id   = "ocr",
            available  = True,
            confidence = 1.0 - best.get("final_text_anomaly_score", 0.5),
            mocked     = False,
            payload    = best,
        )

    def _run_regulatory(self, nafdac_no: str, nafdac_category: str) -> AgentSignal:
        try:
            logger.info("Regulatory | nafdac_no=%s | category=%s", nafdac_no, nafdac_category)
            verdict = self._regulatory_agent.verify(nafdac_no, nafdac_category)
            logger.info(
                "Regulatory complete | status=%s | score=%s | fallback=%s",
                verdict.status_code, verdict.verification_score, verdict.fallback_used,
            )
            return AgentSignal(
                agent_id   = "regulatory",
                available  = True,
                confidence = verdict.verification_score,
                mocked     = False,
                payload    = {
                    "verified":           verdict.verified,
                    "verification_score": verdict.verification_score,
                    "status_code":        verdict.status_code,
                    "severity":           verdict.severity,
                    "summary":            verdict.summary,
                    "detail":             verdict.detail,
                    "expiry_check":       verdict.expiry_check,
                    "alignment":          verdict.alignment,
                    "matched_record":     verdict.matched_record,
                    "all_records":        verdict.all_records,
                    "fallback_used":      verdict.fallback_used,
                    "tools_called":       verdict.tools_called,
                    "reasoning_trace": [
                        {
                            "thought":             step.thought,
                            "action":              step.action,
                            "action_input":        step.action_input,
                            "observation_summary": step.observation_summary,
                        }
                        for step in verdict.reasoning_trace
                    ],
                },
            )
        except Exception:
            logger.error("Regulatory agent failed.", exc_info=True)
            return AgentSignal(
                agent_id   = "regulatory",
                available  = False,
                confidence = 0.0,
                mocked     = False,
                payload    = {
                    "verified":           False,
                    "verification_score": 0.0,
                    "status_code":        "AGENT_ERROR",
                    "severity":           "CRITICAL",
                    "summary":            "Regulatory agent error.",
                    "detail":             "NAFDAC verification unavailable. System fails closed.",
                    "expiry_check":       None,
                    "alignment":          None,
                    "matched_record":     None,
                    "all_records":        [],
                    "fallback_used":      False,
                    "tools_called":       [],
                    "reasoning_trace":    [],
                },
            )

    def _run_vision_multi(self, image_paths: list) -> AgentSignal:
        pipeline = self._visual_pipeline
        if pipeline is None:
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'visual'))
                from vision_engine.pipeline.visual_pipeline import VisualPipeline
                pipeline = VisualPipeline()
                self._visual_pipeline = pipeline
            except Exception as _exc:
                logger.error(
                    "Vision import FAILED — %s: %s. "
                    "Vision signals will be MOCKED. "
                    "Ensure torch, torchvision, ultralytics are installed on this host.",
                    type(_exc).__name__, _exc,
                )
                return self._mock_vision_signal()

        best_result     = None
        best_confidence = -1.0

        for path in image_paths:
            try:
                logger.info("Vision | image=%s", path)
                result = pipeline.analyze(path)
                conf   = result.get("confidence", 0.0)
                logger.info(
                    "Vision image done | product=%s | confidence=%.3f | verdict=%s",
                    result.get("product"), conf, result.get("verdict"),
                )
                # Early exit for no product detected, no point scanning more images
                if result.get("no_product_detected"):
                    logger.info("Vision | NO_PRODUCT_DETECTED — skipping remaining images")
                    return AgentSignal(
                        agent_id   = "vision",
                        available  = True,
                        confidence = 0.0,
                        mocked     = False,
                        payload    = result,
                    )

                if conf > best_confidence:
                    best_confidence = conf
                    best_result     = result
            except Exception:
                logger.warning("Vision failed for %s.", path, exc_info=True)

        if best_result is None:
            return self._mock_vision_signal()

        logger.info("Vision multi complete | %d images | best confidence=%.3f",
                    len(image_paths), best_confidence)
        return AgentSignal(
            agent_id   = "vision",
            available  = True,
            confidence = best_confidence,
            mocked     = False,
            payload    = best_result,
        )

    def _run_fusion(
        self,
        vision_signal:     AgentSignal,
        ocr_signal:        AgentSignal,
        regulatory_signal: AgentSignal,
        gps_coordinates:   dict,
        purchase_channel:  str,
        receipt_image:     Optional[str],
        storefront_image:  Optional[str],
    ) -> AgentSignal:
        logger.info("Fusion | starting...")
        scan_result = run_scan(
            visual_output    = vision_signal.payload,
            ocr_output       = ocr_signal.payload,
            reg_output       = regulatory_signal.payload,
            gps_coordinates  = gps_coordinates,
            purchase_channel = purchase_channel,
            receipt_image    = receipt_image,
            storefront_image = storefront_image,
        )
        logger.info(
            "Fusion complete | verdict=%s | score=%s | status=%s | weight_mode=%s",
            scan_result.get("verdict"), scan_result.get("final_score"),
            scan_result.get("status"), scan_result.get("weight_mode"),
        )
        return AgentSignal(
            agent_id   = "fusion",
            available  = True,
            confidence = scan_result.get("final_score", 0.0),
            mocked     = False,
            payload    = scan_result,
        )

    def _mock_ocr_signal(self) -> AgentSignal:
        return AgentSignal(
            agent_id   = "ocr",
            available  = True,
            confidence = MOCK_CONFIDENCE,
            mocked     = True,
            payload    = {
                "source":                   "OCR_MOCK",
                "final_text_anomaly_score": 1.0 - MOCK_CONFIDENCE,
                "ml_score":                 1.0 - MOCK_CONFIDENCE,
                "metadata": {
                    "nafdac_number":      None,
                    "avg_ocr_confidence": MOCK_CONFIDENCE,
                    "brand_detected":     None,
                    "brand_similarity":   0.0,
                    "brand_anomaly_flag": 0,
                },
                "brand_anomaly": {
                    "brand_detected":        None,
                    "similarity_score":      100.0,
                    "lookalike_corrections": [],
                    "brand_anomaly_flag":    0,
                },
                "structural_validation": {
                    "missing_fields":      [],
                    "structural_score":    1.0,
                    "expiry_format_valid": True,
                    "batch_format_valid":  True,
                },
                "rule_score": {
                    "rule_score":              1.0 - MOCK_CONFIDENCE,
                    "damage_score_applied":    0.1,
                    "adjusted_ocr_confidence": MOCK_CONFIDENCE,
                    "components":              {},
                },
            },
        )

    def _mock_vision_signal(self) -> AgentSignal:
        return AgentSignal(
            agent_id   = "vision",
            available  = True,
            confidence = MOCK_CONFIDENCE,
            mocked     = True,
            payload    = {
                "product":           "UNKNOWN - vision not available",
                "Visual Similarity": MOCK_CONFIDENCE,
                "damage_score":      0.1,
                "blur_value":        80.0,
                "confidence":        MOCK_CONFIDENCE,
                "verdict":           "Authentic" if MOCK_CONFIDENCE >= 0.75 else "Suspicious",
            },
        )

    def explain(self, nafdac_no: str, scanned_category: str) -> str:
        result = self.scan(
            image_path       = "EXPLAIN_MODE_NO_IMAGE",
            nafdac_no        = nafdac_no,
            scanned_category = scanned_category,
            gps_coordinates  = {"lat": 0.0, "lng": 0.0, "accuracy": 0.0},
            purchase_channel = "unknown",
        )
        regulatory_trace = result.regulatory_signal.payload.get("reasoning_trace", [])
        breakdown        = result.breakdown
        lines = [
            "", "SABILENS SCAN - Orchestrator Report", "=" * 60,
            f"NAFDAC    : {nafdac_no}", f"Category  : {scanned_category}",
            f"Scan ID   : {result.scan_id}", f"Status    : {result.status}",
            f"Vision    : {'mocked' if result.vision_signal.mocked else 'real'}",
            f"OCR       : {'mocked' if result.ocr_signal.mocked else 'real'}",
            "Reg       : real (always)", "", "REGULATORY AGENT REASONING", "-" * 40,
        ]
        for i, step in enumerate(regulatory_trace, 1):
            lines += [
                f"  Step {i} | {step['action']}",
                f"    Thought : {step['thought']}",
                f"    Result  : {step['observation_summary']}", "",
            ]
        lines += ["FUSION BREAKDOWN", "-" * 40]
        for signal, data in breakdown.items():
            lines.append(
                f"  {signal:<12} score={data.get('raw_score','n/a')}  "
                f"weight={data.get('weight','n/a')}  weighted={data.get('weighted','n/a')}"
            )
        lines += [
            f"  Override : {result.override_applied}",
            f"  Summary  : {result.override_summary or 'None'}", "",
            "FINAL VERDICT", "-" * 40,
            f"  Verdict    : {result.final_verdict}",
            f"  Score      : {result.final_score}",
            f"  Severity   : {result.final_severity}",
            f"  Action     : {result.action}",
            f"  Instruction: {result.simple_instruction}",
            f"  Warnings   : {[w.get('type') for w in result.warnings]}", "",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    import json

    IMAGE = r"C:\Dev\sabilens\ai_engine\visual\test_images\kelloggs_cornflakes_300g+45g_left.jpg"
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'visual'))
    from vision_engine.damage_detection.damage_detector import DamageDetector
    damage_score = DamageDetector().damage_score(IMAGE)["damage_score"]

    orchestrator = ScanOrchestrator()
    result = orchestrator.scan(
        image_path       = IMAGE,
        nafdac_no        = "",
        scanned_category = "corn flakes",
        gps_coordinates  = {"lat": 6.5244, "lng": 3.3792, "accuracy": 8.5},
        purchase_channel = "open_market",
        damage_score     = damage_score,
    )

    print("\n" + "=" * 60)
    print("SABILENS FULL PIPELINE RESULT")
    print("=" * 60)
    print(f"  Verdict    : {result.final_verdict}")
    print(f"  Score      : {result.final_score}")
    print(f"  Severity   : {result.final_severity}")
    print(f"  Action     : {result.action}")
    print(f"  Instruction: {result.simple_instruction}")
    print(f"  Status     : {result.status}")
    print(f"  Scan ID    : {result.scan_id}")
    print(f"  Vision mocked : {result.vision_signal.mocked}")
    print(f"  OCR mocked    : {result.ocr_signal.mocked}")
    print(f"  Override      : {result.override_applied}")
    print(f"  Warnings      : {[w.get('type') for w in result.warnings]}")
    print(f"  damage_score  : {damage_score}")
    print("\nBREAKDOWN:")
    for signal, data in result.breakdown.items():
        print(f"  {signal:<12} score={data.get('raw_score','n/a')}  "
              f"weight={data.get('weight','n/a')}  weighted={data.get('weighted','n/a')}")
    print("=" * 60)