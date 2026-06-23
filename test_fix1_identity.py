#!/usr/bin/env python3
"""
Fix #1 diagnostic — front-panel-aware identity check.

READ-ONLY: calls the AI engine directly, no HTTP server, no DB writes.
Run from C:\\Dev\\sabilens with a_venv activated:
    python test_fix1_identity.py
"""
import os, sys, re

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
AI_ENGINE  = os.path.join(REPO_ROOT, "ai_engine")
VISUAL_DIR = os.path.join(AI_ENGINE, "visual")
os.chdir(REPO_ROOT)
for _p in (REPO_ROOT, AI_ENGINE, VISUAL_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
for _lg in ("ScanOrchestrator", "OCR_Linguistic", "FusionEngine",
            "NAFDACVerificationAgent", "paddleocr", "ppocr",
            "urllib3", "httpx", "asyncio"):
    logging.getLogger(_lg).setLevel(logging.ERROR)

# ── Imports ───────────────────────────────────────────────────────────────────
print("Loading AI engine (model warm-up, ~30 s)…")

from ai_engine.orchestrator.scan_orchestrator  import ScanOrchestrator
from ai_engine.fusion_engine.signals.visual_adapter import adapt as visual_adapt
from ai_engine.fusion_engine.signals.ocr_adapter    import adapt as ocr_adapt
from ai_engine.fusion_engine.signals.reg_adapter    import adapt as reg_adapt
from ai_engine.fusion_engine.core.fusion_engine     import run_fusion, _name_match, _distinctive_tokens
from ai_engine.fusion_engine.core.decision_classifier import classify

# ── Image roots ───────────────────────────────────────────────────────────────
DOCTORED  = os.path.join(REPO_ROOT, "product_images", "doctored_products")
AUTHENTIC = os.path.join(REPO_ROOT, "product_images", "authentic_products")

# ── Test cases ────────────────────────────────────────────────────────────────
CASES = [
    dict(
        name     = "Fake Cocoa Pups",
        images   = [
            os.path.join(DOCTORED, "Kelloggs_cocoa_pups_360g_front.JPG"),
            os.path.join(DOCTORED, "Kelloggs_cocoa_pups_360g_left.jpg"),
        ],
        category = "Cereals and Cereal Products",
        expected = "FAKE",
        note     = (
            "Fake front (Heffogg's/Cocoa Pups) + genuine back (NAFDAC A8-2361). "
            "ZERO front-panel blocks must match 'KELLOGG'S COCO POPS' at ≥0.85. "
            "Any coincidental match that returns AUTHENTIC is the main risk to expose."
        ),
    ),
    dict(
        name     = "Fake Baseline BleuSeal",
        images   = [
            os.path.join(DOCTORED, "baseline_bleuseal_front.JPG"),
            os.path.join(DOCTORED, "baseline_bleuseal_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "FAKE",
        note     = (
            "Fake front (Baseline/Bleu Seel) + genuine back (NAFDAC 02-0385). "
            "ZERO front-panel blocks must match 'VASELINE BLUE SEAL' at ≥0.85."
        ),
    ),
    dict(
        name     = "Genuine Coco Pops",
        images   = [
            os.path.join(AUTHENTIC, "Kelloggs_coco_pops_360g_front.jpg"),
            os.path.join(AUTHENTIC, "Kelloggs_coco_pops_360g_back.jpg"),
        ],
        category = "Cereals and Cereal Products",
        expected = "AUTHENTIC",
        note     = (
            "'Kellogg's' or 'Coco Pops' on genuine front must hit ≥0.85 "
            "and clear the identity check. Show which block matched."
        ),
    ),
    dict(
        name     = "Genuine CloseUp",
        images   = [
            os.path.join(AUTHENTIC, "closeup_comple_fresh_protection_front.jpg"),
            os.path.join(AUTHENTIC, "closeup_comple_fresh_protection_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "AUTHENTIC",
        note     = "Genuine CloseUp toothpaste. Show which block cleared the threshold.",
    ),
    dict(
        name     = "AXE Body Spray (not in DB)",
        images   = [
            os.path.join(AUTHENTIC, "AXE_bodyspray_150ml_front.jpg"),
            os.path.join(AUTHENTIC, "AXE_bodyspray_150ml_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "SUSPICIOUS",
        note     = (
            "NAFDAC not in DB → fallback_used=True guard must skip identity check. "
            "Must NOT be FAKE from a spurious IDENTITY_MISMATCH."
        ),
    ),
]

# ── Noise filter — same regex as fusion_engine._FRONT_NOISE_RE ───────────────
_NOISE_RE = re.compile(
    r'^\d[\d\.\s+×xX]*\s*(?:g|ml|kg|mg|oz|l|litre|liter)s?\b', re.IGNORECASE
)

def _candidate_blocks(raw_blocks: list) -> list:
    """Apply the same filter _check_name_identity uses for candidate_blocks."""
    return [
        b for b in raw_blocks
        if not b.get("text", "").strip().isdigit()
        and len(b.get("text", "").strip()) > 2
        and not _NOISE_RE.match(b.get("text", "").strip())
    ]

# ── Initialize (once — loads visual model + ChromaDB) ─────────────────────────
orch = ScanOrchestrator()
print("ScanOrchestrator ready.\n")

summary_rows = []

# ═════════════════════════════════════════════════════════════════════════════
for tc in CASES:
    name     = tc["name"]
    category = tc["category"]
    expected = tc["expected"]
    images   = [p for p in tc["images"] if os.path.exists(p)]

    print(f"\n{'━'*72}")
    print(f"CASE    : {name}")
    print(f"EXPECTED: {expected}")
    print(f"Note    : {tc['note']}")
    for p in tc["images"]:
        tag = "✓" if os.path.exists(p) else "✗ MISSING"
        print(f"  [{tag}] {os.path.basename(p)}")
    print()

    if not images:
        print("  SKIP — all images missing.\n")
        summary_rows.append(dict(name=name, expected=expected, actual="SKIP",
                                 result="SKIP", note="images not found"))
        continue

    # ── 1. OCR (all images) → pick best, collect front_panel_blocks ──────────
    ocr_signal         = orch._run_ocr_multi(images, 0.0, orch._retriever)
    payload            = ocr_signal.payload
    nafdac_no          = payload.get("metadata", {}).get("nafdac_number") or ""
    front_panel_blocks = payload.get("front_panel_blocks", [])
    ocr_anomaly        = payload.get("final_text_anomaly_score", 0.5)
    ocr_product_name   = payload.get("metadata", {}).get("product_name") or ""

    print(f"  OCR  → NAFDAC={nafdac_no!r}  product_name={ocr_product_name!r}"
          f"  anomaly={ocr_anomaly:.3f}")
    print(f"         front_panel_blocks collected: {len(front_panel_blocks)} raw blocks")

    # ── 2. Vision ─────────────────────────────────────────────────────────────
    vis_signal = orch._run_vision_multi(images)
    print(f"  VIS  → product={vis_signal.payload.get('product')!r}"
          f"  conf={vis_signal.payload.get('confidence', 0):.3f}"
          f"  mocked={vis_signal.mocked}")

    # ── 3. Regulatory ─────────────────────────────────────────────────────────
    reg_signal    = orch._run_regulatory(nafdac_no, category)
    reg_status    = reg_signal.payload.get("status_code", "?")
    fallback_used = bool(reg_signal.payload.get("fallback_used", False))
    matched       = reg_signal.payload.get("matched_record") or {}
    reg_name      = matched.get("product_name") or ""
    print(f"  REG  → status={reg_status!r}  fallback_used={fallback_used}"
          f"  registered_name={reg_name!r}")

    # ── 4. Adapt & fuse (direct — gives full evidence dict) ───────────────────
    fusion_result    = run_fusion(
        visual_adapt(vis_signal.payload),
        ocr_adapt(payload),
        reg_adapt(reg_signal.payload),
    )
    cls_result       = classify(fusion_result)

    evidence         = fusion_result.get("evidence", {})
    name_id          = evidence.get("name_identity_check", {})
    applied_override = fusion_result.get("applied_override") or {}
    actual_verdict   = cls_result.get("verdict", "?")
    final_score      = cls_result.get("final_score", 0.0)
    simple_instr     = cls_result.get("simple_instruction", "")

    # ── 5. Determine code path taken ─────────────────────────────────────────
    ocr_check = name_id.get("ocr_check") or {}
    if not name_id.get("registered_name"):
        code_path = "SKIPPED — no registered name (fallback_used or NOT_FOUND)"
    elif ocr_check.get("source") == "front_panel":
        code_path = "CHECK (a) — front_panel scan  [two-image path]"
    elif ocr_check.get("source") == "single_image_fallback":
        code_path = "CHECK (a) — single_image_fallback  [one-image path]"
    else:
        code_path = "SKIPPED — fallback_used guard fired (identity check suppressed)"

    # ── 6. Print identity check summary ──────────────────────────────────────
    print(f"\n  ─── IDENTITY CHECK ─────────────────────────────────────────────")
    print(f"  code path        : {code_path}")
    print(f"  registered_name  : {name_id.get('registered_name')!r}")
    print(f"  front_label      : {name_id.get('front_label')!r}"
          f"  ← dominant front block (used in consumer message)")
    print(f"  mismatch_detected: {name_id.get('mismatch_detected')}")
    print(f"  fallback_used    : {fallback_used}"
          f"  ← True means identity check was suppressed (correct for NOT_FOUND)")
    if ocr_check:
        print(f"  ocr_check.source    : {ocr_check.get('source')!r}")
        print(f"  ocr_check.is_match  : {ocr_check.get('is_match')}")
        if ocr_check.get("source") == "front_panel":
            mc  = ocr_check.get("matched_count", 0)
            tc  = ocr_check.get("total_count",   0)
            req = ocr_check.get("required",       0)
            note = ocr_check.get("note", "")
            if note:
                print(f"  NOTE: {note}")
            print(f"  reg_distinctive     : {ocr_check.get('reg_distinctive')}")
            print(f"  front_distinctive   : {ocr_check.get('front_distinctive')}")
            print(f"  matched / total     : {mc} / {tc}  (required={req})")
            prop_pass = (mc >= req) if tc > 0 else False
            print(f"  proportional check  : {'PASS → MATCH' if prop_pass else 'FAIL → MISMATCH'}")
            tok_details = ocr_check.get("token_details") or {}
            if tok_details:
                print(f"\n  Per registered-token results:")
                for reg_tok, hit in sorted(tok_details.items()):
                    if hit:
                        blk = (hit.get("in_block") or "")[:50]
                        print(f"    ✓  {reg_tok!r:<18} → front token {hit.get('front_tok')!r} "
                              f"(block: {blk!r})")
                    else:
                        print(f"    ✗  {reg_tok!r:<18} → NO MATCH on front panel")
        else:
            print(f"  ocr_check.similarity: {ocr_check.get('similarity', 0):.4f}")
    vis_check = name_id.get("visual_check") or {}
    if vis_check:
        print(f"  vis_check.is_match  : {vis_check.get('is_match')}")
        print(f"  vis_check.similarity: {vis_check.get('similarity', 0):.4f}")
    if name_id.get("reason"):
        print(f"  reason: {name_id.get('reason')}")

    # ── 7. Token-breakdown table ──────────────────────────────────────────────
    registered_name = name_id.get("registered_name") or ""
    candidates      = _candidate_blocks(front_panel_blocks)
    noise_removed   = len(front_panel_blocks) - len(candidates)

    print(f"\n  ─── FRONT-PANEL TOKEN AUDIT ────────────────────────────────────")
    print(f"  Raw front_panel_blocks : {len(front_panel_blocks)}")
    print(f"  Noise-filtered away    : {noise_removed}  (digits, weight/volume strings)")
    print(f"  Candidate blocks       : {len(candidates)}")

    if not front_panel_blocks:
        print(f"  (empty — single-image scan OR best image was the only image)")
    elif not registered_name:
        print(f"  (registered_name unknown — skipping token table)")
    else:
        reg_dtok = sorted(_distinctive_tokens(registered_name))
        print(f"\n  Registered name         : {registered_name!r}")
        print(f"  Registered dist. tokens : {reg_dtok}  (min 2 chars, stoplist removed)")
        print()
        print(f"  {'FRONT-PANEL TEXT':<42} {'CONF':>5}  DISTINCTIVE TOKENS")
        print(f"  {'-'*42} {'-'*5}  {'-'*35}")

        sorted_c = sorted(candidates, key=lambda x: x.get("confidence", 0), reverse=True)
        # Build reverse map: front_tok → list of matched registered tokens
        tok_details = (ocr_check or {}).get("token_details") or {}
        front_to_reg: dict = {}
        for reg_tok, hit in tok_details.items():
            if hit and hit.get("front_tok"):
                front_to_reg.setdefault(hit["front_tok"], []).append(reg_tok)

        for b in sorted_c:
            text  = b.get("text", "").strip()
            conf  = b.get("confidence", 0)
            dtoks = sorted(_distinctive_tokens(text))
            annotated = []
            for t in dtoks:
                if t in front_to_reg:
                    annotated.append(f"[✓{t}→{front_to_reg[t]}]")
                else:
                    annotated.append(t)
            tok_str = str(annotated) if annotated else "(all stoplisted or short)"
            print(f"  {text[:42]:<42} {conf:>5.3f}  {tok_str}")

        noise_blocks = [
            b for b in front_panel_blocks
            if b.get("text", "").strip().isdigit()
            or len(b.get("text", "").strip()) <= 2
            or _NOISE_RE.match(b.get("text", "").strip())
        ]
        if noise_blocks:
            print(f"\n  Noise blocks (skipped by filter):")
            for b in noise_blocks:
                print(f"    [{b.get('confidence', 0):.3f}] {b.get('text', '')!r}")

        print()
        if ocr_check and ocr_check.get("source") == "front_panel":
            mc  = ocr_check.get("matched_count", 0)
            tc  = ocr_check.get("total_count",   0)
            req = ocr_check.get("required",       0)
            if tc == 0:
                print(f"  ▶ RESULT: INCONCLUSIVE — registered name has no distinctive tokens")
            elif ocr_check.get("is_match"):
                print(f"  ▶ RESULT: MATCH — {mc}/{tc} registered tokens matched "
                      f"(need {req}) → identity CONSISTENT")
            else:
                print(f"  ▶ RESULT: MISMATCH — only {mc}/{tc} registered tokens matched "
                      f"(need {req}) → IDENTITY_MISMATCH fires")

    # ── 8. Final verdict ──────────────────────────────────────────────────────
    pass_fail = "PASS" if actual_verdict == expected else "FAIL"
    print(f"\n  ─── VERDICT ─────────────────────────────────────────────────────")
    print(f"  actual   : {actual_verdict}  (expected: {expected})")
    print(f"  score    : {final_score}")
    print(f"  weight_mode      : {fusion_result.get('weight_mode')!r}")
    print(f"  override applied : {applied_override.get('type')!r}")
    print(f"  consumer message : {simple_instr}")
    print(f"\n  {'═'*10}  {pass_fail}  {'═'*10}")

    summary_rows.append(dict(
        name     = name,
        expected = expected,
        actual   = actual_verdict,
        result   = pass_fail,
        code_path= code_path,
        mismatch = name_id.get("mismatch_detected", False),
        fallback = fallback_used,
        override = applied_override.get("type", "—"),
    ))

# ═════════════════════════════════════════════════════════════════════════════
print(f"\n\n{'='*72}")
print("SUMMARY")
print(f"{'='*72}")
hdr = f"  {'CASE':<35} {'EXP':<12} {'ACT':<12} {'RESULT':<6}  CODE PATH / OVERRIDE"
print(hdr)
print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*6}  {'-'*36}")
all_pass = True
for r in summary_rows:
    if r["result"] == "FAIL":
        all_pass = False
    note = r.get("override", "—")
    if r.get("mismatch"):
        note = f"IDENTITY_MISMATCH fired ({r['override']})"
    elif r.get("fallback"):
        note = "fallback_used=True → identity check suppressed"
    print(f"  {r['name']:<35} {r['expected']:<12} {r['actual']:<12} "
          f"{r['result']:<6}  {note}")

print(f"\n{'='*72}")
if all_pass:
    print("  Overall: ALL PASS ✓  — safe to deploy and run Playwright suite")
else:
    print("  Overall: FAILURES DETECTED ✗  — fix before deploying")
print(f"{'='*72}\n")
