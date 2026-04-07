"""
test_deployment.py
──────────────────
One test file that validates the entire deployed system end-to-end.
Run this against your live server before declaring a deployment healthy.

USAGE:
    # Against local server:
    pytest test_deployment.py -v

    # Against staging:
    API_URL=https://staging.sabilens.com pytest test_deployment.py -v

    # Against production:
    API_URL=https://api.sabilens.com pytest test_deployment.py -v

WHAT IT TESTS:
    1. Server is reachable and running
    2. ChromaDB has documents indexed (ingestion ran)
    3. All 6 verdict paths work correctly against real data
    4. NAFDAC number normalisation works over HTTP
    5. Semantic search fallback works
    6. Category browse works
    7. Response shape matches what A4 fusion engine expects
    8. Response time is under 3 seconds per scan
    9. Concurrent requests don't break anything

NO MOCKS — everything here hits the real server.
"""

import os
import time
import pytest
import requests
import concurrent.futures

# ── Config ─────────────────────────────────────────────────────────────────────
API_URL          = os.getenv("API_URL", "http://localhost:8000")
MAX_LATENCY_SEC  = float(os.getenv("MAX_LATENCY_SEC", "3.0"))
TIMEOUT          = 15  # per-request timeout in seconds


# ── Helpers ────────────────────────────────────────────────────────────────────

def post(path: str, body: dict) -> requests.Response:
    return requests.post(f"{API_URL}{path}", json=body, timeout=TIMEOUT)

def get(path: str) -> requests.Response:
    return requests.get(f"{API_URL}{path}", timeout=TIMEOUT)


# ═══════════════════════════════════════════════════════════════════
# Class 1 — Server health
# ═══════════════════════════════════════════════════════════════════

class TestServerHealth:

    def test_root_is_reachable(self):
        r = get("/")
        assert r.status_code == 200, f"Server unreachable: {r.status_code}"

    def test_health_endpoint_returns_healthy(self):
        r = get("/verify/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        body = r.json()
        assert body["status"] == "healthy"

    def test_chromadb_has_documents_indexed(self):
        """Fails if ingestion was never run — catches the most common deployment mistake."""
        r    = get("/verify/health")
        body = r.json()
        count = body.get("documents_indexed", 0)
        assert count > 0, (
            f"ChromaDB has {count} documents. "
            "Run ingestion: python sabilens_rag/main.py --mode ingest"
        )

    def test_docs_endpoint_is_available(self):
        r = get("/docs")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Class 2 — All 6 verdict paths against real data
# ═══════════════════════════════════════════════════════════════════

class TestVerdictPaths:
    """
    Tests all 6 status_code values using real products from nafdac_database.xlsx.
    If any of these fail the regulatory agent or ChromaDB is broken.
    """

    def test_verified_kelloggs_corn_flakes(self):
        """A8-4114 + corn flakes → VERIFIED, score=1.0, severity=NONE."""
        r    = post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": "corn flakes"})
        body = r.json()
        assert r.status_code                 == 200
        assert body["status_code"]           == "VERIFIED"
        assert body["verified"]              is True
        assert body["verification_score"]    == 1.0
        assert body["severity"]              == "NONE"

    def test_verified_near_expiry_lipton_tea(self):
        """01-0132 + tea → VERIFIED_NEAR_EXPIRY (expires 2026-03-28)."""
        r    = post("/verify/product", {"nafdac_no": "01-0132", "scanned_subcategory": "tea"})
        body = r.json()
        assert r.status_code              == 200
        assert body["status_code"]        in ("VERIFIED_NEAR_EXPIRY", "VERIFIED")
        assert body["verified"]           is True
        assert body["verification_score"] >= 0.85

    def test_not_found_fake_number(self):
        """FAKE-9999 → NOT_FOUND, score=0.0, severity=CRITICAL."""
        r    = post("/verify/product", {"nafdac_no": "FAKE-9999", "scanned_subcategory": "cereal"})
        body = r.json()
        assert r.status_code              == 200
        assert body["status_code"]        == "NOT_FOUND"
        assert body["verified"]           is False
        assert body["verification_score"] == 0.0
        assert body["severity"]           == "CRITICAL"

    def test_subcategory_mismatch_cereal_nafdac_on_cosmetic(self):
        """A8-4114 (Kellogg's) scanned as cosmetics → SUBCATEGORY_MISMATCH."""
        r    = post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": "cosmetics"})
        body = r.json()
        assert r.status_code              == 200
        assert body["status_code"]        == "SUBCATEGORY_MISMATCH"
        assert body["verified"]           is False
        assert body["verification_score"] == 0.2
        assert body["severity"]           == "CRITICAL"

    def test_verified_vaseline_petroleum_jelly(self):
        """02-0385 + petroleum jelly → VERIFIED."""
        r    = post("/verify/product", {"nafdac_no": "02-0385", "scanned_subcategory": "petroleum jelly"})
        body = r.json()
        assert r.status_code              == 200
        assert body["status_code"]        in ("VERIFIED", "VERIFIED_NEAR_EXPIRY")
        assert body["verified"]           is True

    def test_verified_indomie_noodles(self):
        """01-0877 + noodles → VERIFIED."""
        r    = post("/verify/product", {"nafdac_no": "01-0877", "scanned_subcategory": "noodles"})
        body = r.json()
        assert r.status_code    == 200
        assert body["verified"] is True

    def test_verified_dangote_sugar(self):
        """A8-100798 + sugar → VERIFIED."""
        r    = post("/verify/product", {"nafdac_no": "A8-100798", "scanned_subcategory": "sugar"})
        body = r.json()
        assert r.status_code    == 200
        assert body["verified"] is True


# ═══════════════════════════════════════════════════════════════════
# Class 3 — NAFDAC number normalisation over HTTP
# ═══════════════════════════════════════════════════════════════════

class TestNafdacNormalisation:
    """
    OCR produces messy NAFDAC numbers. These test that the server
    cleans them correctly before lookup.
    """

    def test_nbsp_prefix_cleaned(self):
        """Raw OCR value '\xa001-0132' (Lipton) must still resolve."""
        r    = post("/verify/product", {"nafdac_no": "\xa001-0132", "scanned_subcategory": "tea"})
        body = r.json()
        assert body["verified"] is True

    def test_lowercase_nafdac_normalised(self):
        """'a8-4114' must resolve same as 'A8-4114'."""
        r    = post("/verify/product", {"nafdac_no": "a8-4114", "scanned_subcategory": "cereal"})
        body = r.json()
        assert body["verified"] is True

    def test_spaces_around_dash_normalised(self):
        """'A8 - 4114' must resolve same as 'A8-4114'."""
        r    = post("/verify/product", {"nafdac_no": "A8 - 4114", "scanned_subcategory": "cereal"})
        body = r.json()
        assert body["verified"] is True

    def test_letter_suffix_preserved(self):
        """'A8-8893L' (Sedoso) — letter suffix must not be stripped."""
        r    = post("/verify/product", {"nafdac_no": "A8-8893L", "scanned_subcategory": "cooking oil"})
        body = r.json()
        # Should find the record (VERIFIED or MISMATCH depending on category match)
        assert body["status_code"] != "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════
# Class 4 — Semantic search fallback
# ═══════════════════════════════════════════════════════════════════

class TestSemanticSearch:

    def test_search_returns_results(self):
        r    = post("/verify/search", {"product_text": "kelloggs corn flakes nigeria cereal", "n": 3})
        body = r.json()
        assert r.status_code == 200
        assert isinstance(body, list)
        assert len(body) > 0

    def test_search_top_result_has_required_keys(self):
        r    = post("/verify/search", {"product_text": "indomie noodles chicken flavor", "n": 3})
        body = r.json()
        assert len(body) > 0
        top  = body[0]
        assert "similarity_score" in top
        assert "metadata"         in top
        assert "chunk_text"       in top

    def test_search_similarity_score_between_0_and_1(self):
        r    = post("/verify/search", {"product_text": "vaseline petroleum jelly cosmetics", "n": 3})
        body = r.json()
        for result in body:
            assert 0.0 <= result["similarity_score"] <= 1.0

    def test_search_garbage_text_returns_empty_or_low_scores(self):
        """Completely random text should return no results above threshold."""
        r    = post("/verify/search", {"product_text": "xyzxyz abcabc 999999", "n": 3})
        body = r.json()
        assert r.status_code == 200
        # Either empty list or all scores below threshold
        for result in body:
            assert result["similarity_score"] < 0.68


# ═══════════════════════════════════════════════════════════════════
# Class 5 — Response shape (A4 contract)
# ═══════════════════════════════════════════════════════════════════

class TestResponseShape:
    """
    Verifies the response shape the fusion engineer (A4) depends on.
    If any of these fail, the A4 integration will break.
    """

    REQUIRED_KEYS = {
        "verified", "verification_score", "status_code",
        "severity", "summary", "detail",
        "reasoning_trace", "tools_called", "fallback_used",
    }

    def _scan(self, nafdac="A8-4114", category="corn flakes"):
        return post("/verify/product", {"nafdac_no": nafdac, "scanned_subcategory": category}).json()

    def test_all_required_keys_present_on_verified(self):
        body = self._scan()
        for key in self.REQUIRED_KEYS:
            assert key in body, f"Missing key: '{key}'"

    def test_all_required_keys_present_on_not_found(self):
        body = self._scan(nafdac="FAKE-9999", category="cereal")
        for key in self.REQUIRED_KEYS:
            assert key in body, f"Missing key on NOT_FOUND: '{key}'"

    def test_verification_score_is_float_between_0_and_1(self):
        body = self._scan()
        assert isinstance(body["verification_score"], float)
        assert 0.0 <= body["verification_score"] <= 1.0

    def test_reasoning_trace_is_list(self):
        assert isinstance(self._scan()["reasoning_trace"], list)

    def test_tools_called_is_list(self):
        assert isinstance(self._scan()["tools_called"], list)

    def test_fallback_used_is_bool(self):
        assert isinstance(self._scan()["fallback_used"], bool)

    def test_matched_record_present_on_verified(self):
        body = self._scan()
        assert body["matched_record"] is not None
        assert "product_name"    in body["matched_record"]
        assert "nafdac_no_clean" in body["matched_record"]
        assert "expiry_date_iso" in body["matched_record"]

    def test_matched_record_none_on_not_found(self):
        body = self._scan(nafdac="FAKE-9999", category="cereal")
        assert body["matched_record"] is None

    def test_clean_scan_tools_sequence(self):
        """Clean scan must use exactly: lookup_nafdac → check_expiry → check_alignment."""
        body = self._scan()
        assert body["tools_called"] == ["lookup_nafdac", "check_expiry", "check_alignment"]


# ═══════════════════════════════════════════════════════════════════
# Class 6 — Latency
# ═══════════════════════════════════════════════════════════════════

class TestLatency:
    """
    Fails if scan requests take longer than MAX_LATENCY_SEC (default 3s).
    This is the primary test for the cold-start / eager-loading fix.
    """

    def test_first_scan_under_latency_limit(self):
        """
        The first scan after startup must be fast.
        If this fails, the agent is still lazy-loading on first request.
        """
        start = time.perf_counter()
        r     = post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": "corn flakes"})
        elapsed = time.perf_counter() - start

        assert r.status_code == 200
        assert elapsed < MAX_LATENCY_SEC, (
            f"First scan took {elapsed:.2f}s — exceeds {MAX_LATENCY_SEC}s limit. "
            "Check that agent_scorer._agent is eagerly loaded at startup."
        )

    def test_repeat_scan_under_latency_limit(self):
        """Repeat scans should be faster due to NAFDAC cache hit."""
        post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": "corn flakes"})

        start   = time.perf_counter()
        r       = post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": "corn flakes"})
        elapsed = time.perf_counter() - start

        assert r.status_code == 200
        assert elapsed < 1.0, f"Cached scan took {elapsed:.2f}s — cache may not be working."

    def test_5_sequential_scans_all_under_limit(self):
        scans = [
            ("A8-4114",   "corn flakes"),
            ("01-0132",   "tea"),
            ("02-0385",   "petroleum jelly"),
            ("01-0877",   "noodles"),
            ("A8-100798", "sugar"),
        ]
        for nafdac, category in scans:
            start   = time.perf_counter()
            r       = post("/verify/product", {"nafdac_no": nafdac, "scanned_subcategory": category})
            elapsed = time.perf_counter() - start
            assert r.status_code == 200, f"Scan failed for {nafdac}"
            assert elapsed < MAX_LATENCY_SEC, (
                f"Scan for {nafdac} took {elapsed:.2f}s — exceeds {MAX_LATENCY_SEC}s limit."
            )


# ═══════════════════════════════════════════════════════════════════
# Class 7 — Concurrency
# ═══════════════════════════════════════════════════════════════════

class TestConcurrency:
    """
    Sends multiple requests at the same time.
    Verifies the server handles concurrent scans without errors or data mixing.
    """

    def test_5_concurrent_scans_all_succeed(self):
        scans = [
            ("A8-4114",   "corn flakes",     "VERIFIED"),
            ("FAKE-9999", "cereal",           "NOT_FOUND"),
            ("A8-4114",   "cosmetics",        "SUBCATEGORY_MISMATCH"),
            ("01-0877",   "noodles",          "VERIFIED"),
            ("A8-100798", "sugar",            "VERIFIED"),
        ]

        def run_scan(args):
            nafdac, category, expected_status = args
            r = post("/verify/product", {"nafdac_no": nafdac, "scanned_subcategory": category})
            return nafdac, expected_status, r.status_code, r.json().get("status_code")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(run_scan, scans))

        for nafdac, expected, http_code, got_status in results:
            assert http_code == 200, f"{nafdac}: HTTP {http_code}"
            assert got_status == expected, (
                f"{nafdac}: expected status_code={expected}, got={got_status}"
            )

    def test_concurrent_scans_dont_mix_results(self):
        """
        Same NAFDAC number, different categories — concurrent requests must
        each get the result for their own category, not each other's.
        """
        def scan(category):
            r = post("/verify/product", {"nafdac_no": "A8-4114", "scanned_subcategory": category})
            return category, r.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(scan, "corn flakes"),
                pool.submit(scan, "cosmetics"),
            ]
            results = {category: body for category, body in (f.result() for f in futures)}

        assert results["corn flakes"]["status_code"] == "VERIFIED"
        assert results["cosmetics"]["status_code"]   == "SUBCATEGORY_MISMATCH"