"""
Five-case identity check verification -- ASCII output only.
Tests proportional token-matching across all five cases.
Do NOT modify any engine files. Do NOT commit.

Genuine Coco Pops pairing corrected:
  front = authentic_products/Kelloggs_coco_pops_360g_front.jpg
  nafdac-panel = authentic_products/Kelloggs_coco_pops_360g_left.jpg
  (back/nutrition face replaced -- it has no NAFDAC line)
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

print("Loading AI engine (model warm-up, ~30s)...")

from ai_engine.orchestrator.scan_orchestrator       import ScanOrchestrator
from ai_engine.fusion_engine.signals.visual_adapter import adapt as visual_adapt
from ai_engine.fusion_engine.signals.ocr_adapter    import adapt as ocr_adapt
from ai_engine.fusion_engine.signals.reg_adapter    import adapt as reg_adapt
from ai_engine.fusion_engine.core.fusion_engine     import run_fusion, _name_match, _distinctive_tokens
from ai_engine.fusion_engine.core.decision_classifier import classify

DOCTORED  = os.path.join(REPO_ROOT, "product_images", "doctored_products")
AUTHENTIC = os.path.join(REPO_ROOT, "product_images", "authentic_products")

# ---------------------------------------------------------------
# Test cases
# NOTE: Genuine Coco Pops now uses left panel (has NAFDAC A8-2361),
#       NOT the back/nutrition face (confirmed empty by diagnostic).
# ---------------------------------------------------------------
CASES = [
    dict(
        name     = "Fake Cocoa Pups",
        images   = [
            os.path.join(DOCTORED, "Kelloggs_cocoa_pups_360g_front.JPG"),
            os.path.join(DOCTORED, "Kelloggs_cocoa_pups_360g_left.jpg"),
        ],
        category = "Cereals and Cereal Products",
        expected = "FAKE",
        reason   = ("matched 1 / (>=2 needed): only 'coco' matches; "
                    "'pops' and 'kellogg' miss. Must FAIL on multiple token misses, "
                    "NOT a fallback score."),
    ),
    dict(
        name     = "Fake Baseline BleuSeal",
        images   = [
            os.path.join(DOCTORED, "baseline_bleuseal_front.JPG"),
            os.path.join(DOCTORED, "baseline_bleuseal_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "FAKE",
        reason   = "matched 0/2: neither 'vaseline' nor 'blueseal' matches.",
    ),
    dict(
        name     = "Genuine Coco Pops",
        images   = [
            # front.jpg  -- genuine brand panel
            os.path.join(AUTHENTIC, "Kelloggs_coco_pops_360g_front.jpg"),
            # left.jpg   -- confirmed NAFDAC A8-2361 at conf 0.9678 (diagnostic)
            os.path.join(AUTHENTIC, "Kelloggs_coco_pops_360g_left.jpg"),
        ],
        category = "Cereals and Cereal Products",
        expected = "AUTHENTIC",
        reason   = ("NAFDAC A8-2361 from left panel -> fallback_used=False -> "
                    "identity check RUNS -> 'coco'+'pops' match as exact tokens -> "
                    "matched >= required -> AUTHENTIC. "
                    "Path must be front-panel proportional, NOT fallback."),
    ),
    dict(
        name     = "Genuine CloseUp",
        images   = [
            os.path.join(AUTHENTIC, "closeup_comple_fresh_protection_front.jpg"),
            os.path.join(AUTHENTIC, "closeup_comple_fresh_protection_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "AUTHENTIC",
        reason   = "'closeup' matches 1/1 registered token; check (b) skipped via Fix C.",
    ),
    dict(
        name     = "AXE Body Spray (not in DB)",
        images   = [
            os.path.join(AUTHENTIC, "AXE_bodyspray_150ml_front.jpg"),
            os.path.join(AUTHENTIC, "AXE_bodyspray_150ml_back.jpg"),
        ],
        category = "Cosmetics",
        expected = "SUSPICIOUS",
        reason   = "NAFDAC not in DB -> fallback_used=True -> identity check suppressed.",
    ),
]

# Noise filter (mirrors fusion_engine._FRONT_NOISE_RE)
_NOISE_RE = re.compile(
    r'^\d[\d\.\s+x]*\s*(?:g|ml|kg|mg|oz|l|litre|liter)s?\b', re.IGNORECASE
)

def _candidate_blocks(raw_blocks):
    return [
        b for b in raw_blocks
        if not b.get("text", "").strip().isdigit()
        and len(b.get("text", "").strip()) > 2
        and not _NOISE_RE.match(b.get("text", "").strip())
    ]

orch = ScanOrchestrator()
print("ScanOrchestrator ready.")
print()

summary_rows = []

for tc in CASES:
    name     = tc["name"]
    category = tc["category"]
    expected = tc["expected"]

    print("=" * 72)
    print("CASE    : {}".format(name))
    print("EXPECTED: {}".format(expected))
    print("REASON  : {}".format(tc["reason"]))
    print()

    # -- File existence check --
    print("  Images (full paths):")
    for p in tc["images"]:
        exists = os.path.isfile(p)
        tag    = "EXISTS" if exists else "MISSING"
        print("    [{}] {}".format(tag, p))
    print()

    images = [p for p in tc["images"] if os.path.isfile(p)]
    if not images:
        print("  SKIP -- all images missing.")
        summary_rows.append(dict(
            name=name, expected=expected, actual="SKIP",
            result="SKIP", code_path="n/a", mismatch=False,
            fallback=False, override="n/a"
        ))
        print()
        continue

    # -- 1. OCR --
    ocr_signal         = orch._run_ocr_multi(images, 0.0, orch._retriever)
    payload            = ocr_signal.payload
    nafdac_no          = payload.get("metadata", {}).get("nafdac_number") or ""
    front_panel_blocks = payload.get("front_panel_blocks", [])
    ocr_anomaly        = payload.get("final_text_anomaly_score", 0.5)
    ocr_product_name   = payload.get("metadata", {}).get("product_name") or ""

    print("  OCR -> NAFDAC={!r}  product_name={!r}  anomaly={:.3f}".format(
        nafdac_no, ocr_product_name, ocr_anomaly))
    print("         front_panel_blocks: {} raw blocks".format(len(front_panel_blocks)))

    # -- 2. Vision --
    vis_signal = orch._run_vision_multi(images)
    print("  VIS -> product={!r}  conf={:.3f}  mocked={}".format(
        vis_signal.payload.get("product"),
        vis_signal.payload.get("confidence", 0),
        vis_signal.mocked,
    ))

    # -- 3. Regulatory --
    reg_signal    = orch._run_regulatory(nafdac_no, category)
    reg_status    = reg_signal.payload.get("status_code", "?")
    fallback_used = bool(reg_signal.payload.get("fallback_used", False))
    matched_rec   = reg_signal.payload.get("matched_record") or {}
    reg_name      = matched_rec.get("product_name") or ""
    print("  REG -> status={!r}  fallback_used={}  registered_name={!r}".format(
        reg_status, fallback_used, reg_name))

    # -- 4. Fuse --
    fusion_result = run_fusion(
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

    # -- 5. Code path --
    ocr_check = name_id.get("ocr_check") or {}
    if not name_id.get("registered_name"):
        code_path = "SKIPPED -- no registered name (fallback_used or NOT_FOUND)"
    elif ocr_check.get("source") == "front_panel":
        code_path = "CHECK(a) -- front_panel proportional scan [two-image path]"
    elif ocr_check.get("source") == "single_image_fallback":
        code_path = "CHECK(a) -- single_image_fallback [one-image path]"
    else:
        code_path = "SKIPPED -- fallback_used guard fired (identity check suppressed)"

    # -- 6. Identity check block --
    print()
    print("  --- IDENTITY CHECK ---")
    print("  code path        : {}".format(code_path))
    print("  registered_name  : {!r}".format(name_id.get("registered_name")))
    print("  front_label      : {!r}  <- dominant front block".format(name_id.get("front_label")))
    print("  mismatch_detected: {}".format(name_id.get("mismatch_detected")))
    print("  fallback_used    : {}  <- True means identity check was suppressed".format(fallback_used))

    if ocr_check:
        print("  ocr_check.source   : {!r}".format(ocr_check.get("source")))
        print("  ocr_check.is_match : {}".format(ocr_check.get("is_match")))
        if ocr_check.get("source") == "front_panel":
            mc   = ocr_check.get("matched_count", 0)
            tot  = ocr_check.get("total_count",   0)
            req  = ocr_check.get("required",       0)
            note = ocr_check.get("note", "")
            if note:
                print("  NOTE: {}".format(note))
            print("  reg_distinctive  : {}".format(ocr_check.get("reg_distinctive")))
            print("  front_distinctive: {}".format(ocr_check.get("front_distinctive")))
            print("  matched / total  : {} / {}  (required={})".format(mc, tot, req))
            prop_pass = (mc >= req) if tot > 0 else False
            print("  proportional check: {}".format(
                "PASS -> MATCH" if prop_pass else "FAIL -> MISMATCH"))
            tok_details = ocr_check.get("token_details") or {}
            if tok_details:
                print()
                print("  Per registered-token results:")
                for reg_tok, hit in sorted(tok_details.items()):
                    if hit:
                        blk = (hit.get("in_block") or "")[:50]
                        print("    [x]  {:<18} -> front token {!r}  (block: {!r})".format(
                            repr(reg_tok), hit.get("front_tok"), blk))
                    else:
                        print("    [ ]  {:<18} -> NO MATCH on front panel".format(repr(reg_tok)))
        else:
            print("  ocr_check.similarity: {:.4f}".format(ocr_check.get("similarity", 0)))

    vis_check = name_id.get("visual_check") or {}
    if vis_check:
        print("  vis_check.is_match  : {}".format(vis_check.get("is_match")))
        print("  vis_check.similarity: {:.4f}".format(vis_check.get("similarity", 0)))
    if name_id.get("reason"):
        print("  reason: {}".format(name_id.get("reason")))

    # -- 7. Front-panel token audit --
    registered_name = name_id.get("registered_name") or ""
    candidates      = _candidate_blocks(front_panel_blocks)
    noise_removed   = len(front_panel_blocks) - len(candidates)

    print()
    print("  --- FRONT-PANEL TOKEN AUDIT ---")
    print("  Raw front_panel_blocks : {}".format(len(front_panel_blocks)))
    print("  Noise-filtered away    : {}  (digits, weight/volume strings)".format(noise_removed))
    print("  Candidate blocks       : {}".format(len(candidates)))

    if not front_panel_blocks:
        print("  (empty -- single-image scan or best image was the only image)")
    elif not registered_name:
        print("  (registered_name unknown -- skipping token table)")
    else:
        reg_dtok = sorted(_distinctive_tokens(registered_name))
        print()
        print("  Registered name         : {!r}".format(registered_name))
        print("  Registered dist. tokens : {}  (min 2 chars, stoplist removed)".format(reg_dtok))
        print()
        print("  {:<42} {:>5}  DISTINCTIVE TOKENS".format("FRONT-PANEL TEXT", "CONF"))
        print("  {} {}  {}".format("-"*42, "-"*5, "-"*35))

        sorted_c = sorted(candidates, key=lambda x: x.get("confidence", 0), reverse=True)
        tok_details = (ocr_check or {}).get("token_details") or {}
        front_to_reg = {}
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
                    annotated.append("[x {}->{}]".format(t, front_to_reg[t]))
                else:
                    annotated.append(t)
            tok_str = str(annotated) if annotated else "(all stoplisted or short)"
            print("  {:<42} {:>5.3f}  {}".format(text[:42], conf, tok_str))

        noise_blocks = [
            b for b in front_panel_blocks
            if b.get("text", "").strip().isdigit()
            or len(b.get("text", "").strip()) <= 2
            or _NOISE_RE.match(b.get("text", "").strip())
        ]
        if noise_blocks:
            print()
            print("  Noise blocks (skipped by filter):")
            for b in noise_blocks:
                print("    [{:.3f}] {!r}".format(b.get("confidence", 0), b.get("text", "")))

        print()
        if ocr_check and ocr_check.get("source") == "front_panel":
            mc  = ocr_check.get("matched_count", 0)
            tot = ocr_check.get("total_count",   0)
            req = ocr_check.get("required",       0)
            if tot == 0:
                print("  > RESULT: INCONCLUSIVE -- registered name has no distinctive tokens")
            elif ocr_check.get("is_match"):
                print("  > RESULT: MATCH -- {}/{} registered tokens matched "
                      "(need {}) -> identity CONSISTENT".format(mc, tot, req))
            else:
                print("  > RESULT: MISMATCH -- only {}/{} registered tokens matched "
                      "(need {}) -> IDENTITY_MISMATCH fires".format(mc, tot, req))

    # -- 8. Verdict --
    pass_fail = "PASS" if actual_verdict == expected else "FAIL"
    print()
    print("  --- VERDICT ---")
    print("  actual   : {}  (expected: {})".format(actual_verdict, expected))
    print("  score    : {}".format(final_score))
    print("  weight_mode      : {!r}".format(fusion_result.get("weight_mode")))
    print("  override applied : {!r}".format(applied_override.get("type")))
    print("  consumer message : {}".format(simple_instr))
    print()
    print("  >>>  {}  <<<".format(pass_fail))
    print()

    summary_rows.append(dict(
        name      = name,
        expected  = expected,
        actual    = actual_verdict,
        result    = pass_fail,
        code_path = code_path,
        mismatch  = name_id.get("mismatch_detected", False),
        fallback  = fallback_used,
        override  = applied_override.get("type", "--"),
    ))

# ---------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------
print()
print("=" * 72)
print("SUMMARY")
print("=" * 72)
print("  {:<35} {:<12} {:<12} {:<6}  CODE PATH / OVERRIDE".format(
    "CASE", "EXPECTED", "ACTUAL", "RESULT"))
print("  {} {} {} {}  {}".format("-"*35, "-"*12, "-"*12, "-"*6, "-"*36))

all_pass = True
for r in summary_rows:
    if r["result"] == "FAIL":
        all_pass = False
    note = r.get("override", "--")
    if r.get("mismatch"):
        note = "IDENTITY_MISMATCH fired ({})".format(r["override"])
    elif r.get("fallback"):
        note = "fallback_used=True -> identity check suppressed"
    print("  {:<35} {:<12} {:<12} {:<6}  {}".format(
        r["name"], r["expected"], r["actual"], r["result"], note))

print()
print("=" * 72)
if all_pass:
    print("  Overall: ALL PASS -- safe to deploy and run Playwright suite")
else:
    print("  Overall: FAILURES DETECTED -- fix before deploying")
print("=" * 72)
print()
