"""
RAG System — Stronger Test Suite
===================================

Deeper correctness tests for the NAFDAC product ingestion and retrieval pipeline.
Complements test_nafdac_normalizer.py, test_chunk_builder.py, and
test_subcategory_alignment.py with precision tests that verify exact contract
details rather than just happy-path behaviour.

Groups:
  A — Normalizer exhaustive edge cases    (every documented edge case in nafdac_normalizer.py)
  B — is_valid_nafdac_no() function       (post-normalisation validation helper)
  C — Chunk text template precision       (exact field labels in the embedding text)
  D — Chunk ID (MD5) contract             (format, determinism, collision-resistance)
  E — Chunk metadata contract             (ChromaDB string requirement + all keys)
  F — build_chunks() statistics accuracy  (total, duplicates, subcategory, null counts)
  G — ProductChunk model_dump()           (serialisation contract for save_chunks)
  H — save_chunks() JSON file contract    (file structure, deep-path creation, encoding)
  I — NAFDACEntry schema contract         (dataclass fields, all subcategory values)
  J — Null/missing/empty sentinel handling (normalizer + chunk builder edge inputs)

Run:
    pytest ai_engine/rag_system/tests/test_rag_strong.py -v
"""

import sys
import os
import json
import hashlib
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from ingestion.schema      import NAFDACEntry, ProductChunk, VALID_SUBCATEGORIES
from ingestion.chunk_builder import (
    build_chunks, save_chunks, _build_chunk_id, _build_text,
)
from utils.nafdac_normalizer import normalize_nafdac_no, is_valid_nafdac_no


# ── Shared entry factory ───────────────────────────────────────────────────────

def make_entry(**kwargs) -> NAFDACEntry:
    """Build a NAFDACEntry with sensible defaults, overridable by kwargs."""
    defaults = dict(
        nafdac_no          = "A8-4114",
        nafdac_no_clean    = "A8-4114",
        product_name       = "KELLOGG'S CORN FLAKES",
        product_name_upper = "KELLOGG'S CORN FLAKES",
        subcategory        = "Cereals and Cereal Products",
        subcategory_lower  = "cereals and cereal products",
        presentation       = "300G HARDBOARD PACK",
        applicant_name     = "KELLOGG TOLARAM NIGERIA LIMTED",
        country            = "Nigeria",
        manufacturer       = "KT LFTZ ENTERPRISE",
        expiry_date_raw    = "2029-07-30 00:00:00",
        expiry_date_iso    = "2029-07-30",
    )
    defaults.update(kwargs)
    return NAFDACEntry(**defaults)


# Pre-built fixtures
CORN_FLAKES = make_entry()
VASELINE    = make_entry(
    nafdac_no="02-0385", nafdac_no_clean="02-0385",
    product_name="Vaseline blueseal pure petroleum jelly original",
    product_name_upper="VASELINE BLUESEAL PURE PETROLEUM JELLY ORIGINAL",
    subcategory="Cosmetics", subcategory_lower="cosmetics",
    presentation="Light yellow gel with a blue cover and transparent body PET 225ml",
    applicant_name="UNILEVER NIGERIA PLC",
    manufacturer="UNILEVER NIGERIA PLC",
    expiry_date_iso="2028-12-20",
)
DANGOTE = make_entry(
    nafdac_no="A8-100798", nafdac_no_clean="A8-100798",
    product_name="DANGOTE SUGAR REFINED GRANULATED WHITE SUGAR",
    product_name_upper="DANGOTE SUGAR REFINED GRANULATED WHITE SUGAR",
    subcategory="Sweeteners", subcategory_lower="sweeteners",
    presentation="",   # intentionally empty
    applicant_name="DANGOTE SUGAR REFINERY PLC",
    manufacturer="Dangote Sugar refinery Plc",
    expiry_date_iso="2027-01-26",
)
LIPTON = make_entry(
    nafdac_no="01-0132", nafdac_no_clean="01-0132",
    product_name="LIPTON YELLOW LABEL TEA", product_name_upper="LIPTON YELLOW LABEL TEA",
    subcategory="Beverages", subcategory_lower="beverages",
    presentation="25 x 2.0g in Hard board pack",
    applicant_name="UNILEVER NIGERIA PLC",
    manufacturer="UNILEVER NIG. PLC",
    expiry_date_iso="2026-03-28",
)


# ── GROUP A: Normalizer Exhaustive Edge Cases ──────────────────────────────────

class TestNormalizerExhaustive:
    """Every documented edge case from nafdac_normalizer.py docstring."""

    # Standard forms — must pass through unchanged (after uppercasing)
    def test_alpha_prefix_standard(self):
        assert normalize_nafdac_no("A8-4114") == "A8-4114"

    def test_numeric_prefix_standard(self):
        assert normalize_nafdac_no("01-0132") == "01-0132"

    def test_long_serial_alpha_prefix(self):
        assert normalize_nafdac_no("A8-100798") == "A8-100798"

    def test_long_serial_numeric_prefix(self):
        assert normalize_nafdac_no("A2-102856") == "A2-102856"

    def test_letter_suffix_preserved(self):
        assert normalize_nafdac_no("A8-8893L") == "A8-8893L"

    def test_lowercase_input_is_uppercased(self):
        assert normalize_nafdac_no("a8-4114") == "A8-4114"

    def test_mixed_case_input_is_uppercased(self):
        assert normalize_nafdac_no("A8-8893l") == "A8-8893L"

    # Unicode whitespace (NBSP prefix — real data in nafdac_database.xlsx)
    def test_nbsp_prefix_row_2_stripped(self):
        """Row 2: '\xa001-0132' → '01-0132'"""
        assert normalize_nafdac_no("\xa001-0132") == "01-0132"

    def test_nbsp_prefix_row_9_stripped(self):
        """Row 9: '\xa002-8608' → '02-8608'"""
        assert normalize_nafdac_no("\xa002-8608") == "02-8608"

    def test_nbsp_with_alpha_prefix_stripped(self):
        assert normalize_nafdac_no("\xa0A8-4114") == "A8-4114"

    # Dash variants
    def test_en_dash_normalised(self):
        """U+2013 en-dash → ASCII hyphen"""
        assert normalize_nafdac_no("04\u20132045") == "04-2045"

    def test_em_dash_normalised(self):
        """U+2014 em-dash → ASCII hyphen"""
        assert normalize_nafdac_no("A8\u20144114") == "A8-4114"

    def test_minus_sign_normalised(self):
        """U+2212 minus → ASCII hyphen"""
        assert normalize_nafdac_no("01\u22120132") == "01-0132"

    # Spaced-dash variants
    def test_spaced_dash_a4_style(self):
        """'A4 - 5180' → 'A4-5180'"""
        assert normalize_nafdac_no("A4 - 5180") == "A4-5180"

    def test_spaced_dash_numeric_prefix(self):
        """'04 - 1508' → '04-1508'"""
        assert normalize_nafdac_no("04 - 1508") == "04-1508"

    def test_spaced_dash_no_spaces_passes_directly(self):
        assert normalize_nafdac_no("A4-5180") == "A4-5180"

    # Slash format (legacy)
    def test_slash_format_basic(self):
        """'4/1/9086' → '4-9086'"""
        assert normalize_nafdac_no("4/1/9086") == "4-9086"

    def test_slash_format_with_letter_suffix(self):
        """'4/2/9086L' → '4-9086L'"""
        result = normalize_nafdac_no("4/2/9086L")
        assert result is not None
        assert result.endswith("L")

    # Null sentinels — must return None
    def test_empty_string_returns_none(self):
        assert normalize_nafdac_no("") is None

    def test_na_sentinel_returns_none(self):
        assert normalize_nafdac_no("NA") is None

    def test_na_lowercase_returns_none(self):
        assert normalize_nafdac_no("na") is None

    def test_n_slash_a_returns_none(self):
        assert normalize_nafdac_no("n/a") is None

    def test_nan_returns_none(self):
        assert normalize_nafdac_no("NaN") is None

    def test_none_returns_none(self):
        assert normalize_nafdac_no("none") is None

    def test_null_returns_none(self):
        assert normalize_nafdac_no("null") is None

    def test_single_dash_returns_none(self):
        assert normalize_nafdac_no("-") is None

    def test_not_available_returns_none(self):
        assert normalize_nafdac_no("not available") is None

    def test_not_available_yet_returns_none(self):
        assert normalize_nafdac_no("not available yet") is None

    def test_python_none_returns_none(self):
        assert normalize_nafdac_no(None) is None

    # NBSP + null sentinel
    def test_nbsp_plus_dash_returns_none(self):
        """'\xa0-' → stripped to '-' → null sentinel → None"""
        assert normalize_nafdac_no("\xa0-") is None

    # Non-NAFDAC garbage
    def test_random_text_returns_none(self):
        assert normalize_nafdac_no("HELLO WORLD") is None

    def test_only_digits_no_hyphen_returns_none(self):
        assert normalize_nafdac_no("12345") is None


# ── GROUP B: is_valid_nafdac_no() ─────────────────────────────────────────────

class TestIsValidNafdacNo:
    """is_valid_nafdac_no() checks canonical form AFTER normalisation."""

    def test_canonical_alpha_prefix_is_valid(self):
        assert is_valid_nafdac_no("A8-4114") is True

    def test_canonical_numeric_prefix_is_valid(self):
        assert is_valid_nafdac_no("01-0132") is True

    def test_canonical_letter_suffix_is_valid(self):
        assert is_valid_nafdac_no("A8-8893L") is True

    def test_long_serial_is_valid(self):
        assert is_valid_nafdac_no("A8-100798") is True

    def test_none_is_invalid(self):
        assert is_valid_nafdac_no(None) is False

    def test_empty_string_is_invalid(self):
        assert is_valid_nafdac_no("") is False

    def test_raw_with_spaces_is_invalid(self):
        """Raw (un-normalised) 'A8 - 4114' must not validate — call normalize first."""
        assert is_valid_nafdac_no("A8 - 4114") is False

    def test_lowercase_is_invalid(self):
        assert is_valid_nafdac_no("a8-4114") is False


# ── GROUP C: Chunk Text Template Precision ────────────────────────────────────

class TestChunkTextTemplate:
    """Every field label in the embedding text template must be exactly correct."""

    def test_product_label_present(self):
        assert "Product:" in _build_text(CORN_FLAKES)

    def test_nafdac_no_label_present(self):
        assert "NAFDAC No:" in _build_text(CORN_FLAKES)

    def test_category_label_present(self):
        assert "Category:" in _build_text(CORN_FLAKES)

    def test_applicant_label_present(self):
        assert "Applicant:" in _build_text(CORN_FLAKES)

    def test_manufacturer_label_present(self):
        assert "Manufacturer:" in _build_text(CORN_FLAKES)

    def test_presentation_label_present_when_not_empty(self):
        assert "Presentation:" in _build_text(CORN_FLAKES)

    def test_country_label_present(self):
        assert "Country:" in _build_text(CORN_FLAKES)

    def test_expiry_date_label_present(self):
        assert "Expiry Date:" in _build_text(CORN_FLAKES)

    def test_presentation_label_absent_when_empty(self):
        """Dangote Sugar has an empty presentation — 'Presentation:' must not appear."""
        text = _build_text(DANGOTE)
        assert "Presentation:" not in text

    def test_nafdac_no_value_embedded_correctly(self):
        assert "A8-4114" in _build_text(CORN_FLAKES)

    def test_subcategory_value_embedded_correctly(self):
        assert "Cereals and Cereal Products" in _build_text(CORN_FLAKES)

    def test_applicant_name_embedded(self):
        assert "KELLOGG TOLARAM" in _build_text(CORN_FLAKES)

    def test_manufacturer_embedded(self):
        assert "KT LFTZ ENTERPRISE" in _build_text(CORN_FLAKES)

    def test_expiry_date_iso_embedded(self):
        assert "2029-07-30" in _build_text(CORN_FLAKES)

    def test_country_embedded(self):
        assert "Nigeria" in _build_text(CORN_FLAKES)

    def test_long_presentation_fully_included(self):
        """Vaseline's 66-char presentation must appear in full for semantic search."""
        text = _build_text(VASELINE)
        assert "Light yellow gel with a blue cover" in text
        assert "PET 225ml" in text

    def test_text_ends_with_period(self):
        """Template ends with '.' after the last field."""
        assert _build_text(CORN_FLAKES).endswith(".")

    def test_fields_separated_by_period_space(self):
        """Fields are joined by '. ' (period + space)."""
        text = _build_text(CORN_FLAKES)
        assert ". " in text

    def test_no_nafdac_shows_not_available(self):
        """When nafdac_no_clean is empty AND nafdac_no is empty, text shows 'Not available'."""
        no_nafdac = make_entry(nafdac_no="", nafdac_no_clean="")
        text = _build_text(no_nafdac)
        assert "Not available" in text


# ── GROUP D: Chunk ID (MD5) Contract ──────────────────────────────────────────

class TestChunkIdContract:
    """chunk_id must be a 32-char lowercase MD5 hex string, deterministic and unique."""

    def test_chunk_id_is_32_chars(self):
        assert len(_build_chunk_id("A8-4114", "KELLOGG'S CORN FLAKES")) == 32

    def test_chunk_id_is_lowercase_hex(self):
        cid = _build_chunk_id("A8-4114", "KELLOGG'S CORN FLAKES")
        assert all(c in "0123456789abcdef" for c in cid)

    def test_chunk_id_matches_expected_md5(self):
        """Verify the exact MD5 formula: md5(nafdac_no_clean + '|' + product_name_upper)."""
        raw = "A8-4114|KELLOGG'S CORN FLAKES"
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        assert _build_chunk_id("A8-4114", "KELLOGG'S CORN FLAKES") == expected

    def test_deterministic_same_id_on_repeated_calls(self):
        id1 = _build_chunk_id("A8-4114", "KELLOGG'S CORN FLAKES")
        id2 = _build_chunk_id("A8-4114", "KELLOGG'S CORN FLAKES")
        assert id1 == id2

    def test_different_nafdac_produces_different_id(self):
        id1 = _build_chunk_id("A8-4114", "PRODUCT X")
        id2 = _build_chunk_id("A8-2361", "PRODUCT X")
        assert id1 != id2

    def test_different_product_produces_different_id(self):
        id1 = _build_chunk_id("A8-4114", "PRODUCT A")
        id2 = _build_chunk_id("A8-4114", "PRODUCT B")
        assert id1 != id2

    def test_empty_nafdac_still_produces_id(self):
        """Null-nafdac rows still get a stable 32-char ID."""
        cid = _build_chunk_id("", "SOME PRODUCT")
        assert len(cid) == 32

    def test_whitespace_stripped_from_product_name(self):
        """Leading/trailing whitespace in product_name_upper must be stripped before hashing."""
        id_normal = _build_chunk_id("A8-4114", "CORN FLAKES")
        id_padded = _build_chunk_id("A8-4114", "  CORN FLAKES  ")
        assert id_normal == id_padded


# ── GROUP E: Chunk Metadata Contract ──────────────────────────────────────────

class TestChunkMetadataContract:
    """ChromaDB requires all metadata values to be plain strings — no None, int, bool."""

    def _first_chunk(self, entry=None):
        chunks, _ = build_chunks([entry or CORN_FLAKES])
        return chunks[0]

    def test_all_metadata_values_are_str(self):
        chunk = self._first_chunk()
        for key, val in chunk.metadata.items():
            assert isinstance(val, str), \
                f"metadata['{key}'] is {type(val).__name__}, expected str"

    def test_all_required_metadata_keys_present(self):
        chunk = self._first_chunk()
        required = {
            "nafdac_no", "nafdac_no_clean", "product_name", "product_name_upper",
            "subcategory", "presentation", "applicant_name", "country",
            "manufacturer", "expiry_date_raw", "expiry_date_iso",
        }
        assert required.issubset(set(chunk.metadata.keys()))

    def test_metadata_values_match_entry_fields(self):
        chunk = self._first_chunk()
        assert chunk.metadata["nafdac_no_clean"]   == "A8-4114"
        assert chunk.metadata["product_name"]      == "KELLOGG'S CORN FLAKES"
        assert chunk.metadata["subcategory"]       == "Cereals and Cereal Products"
        assert chunk.metadata["country"]           == "Nigeria"
        assert chunk.metadata["expiry_date_iso"]   == "2029-07-30"

    def test_empty_presentation_stored_as_empty_string_not_none(self):
        """An empty presentation must be stored as '' (str), not None."""
        chunk = self._first_chunk(DANGOTE)
        assert chunk.metadata["presentation"] == ""
        assert isinstance(chunk.metadata["presentation"], str)

    def test_subcategory_denormalised_field_matches_metadata(self):
        chunk = self._first_chunk(VASELINE)
        assert chunk.subcategory == chunk.metadata["subcategory"] == "Cosmetics"

    def test_nafdac_no_clean_denormalised_field_matches_metadata(self):
        chunk = self._first_chunk()
        assert chunk.nafdac_no_clean == chunk.metadata["nafdac_no_clean"]

    def test_expiry_date_iso_denormalised_field_matches_metadata(self):
        chunk = self._first_chunk()
        assert chunk.expiry_date_iso == chunk.metadata["expiry_date_iso"]


# ── GROUP F: build_chunks() Statistics Accuracy ──────────────────────────────

class TestBuildChunksStats:
    """Stats dict must accurately reflect what was built."""

    def test_total_entries_processed_matches_input_length(self):
        _, stats = build_chunks([CORN_FLAKES, VASELINE, LIPTON])
        assert stats["total_entries_processed"] == 3

    def test_chunks_built_excludes_duplicates(self):
        _, stats = build_chunks([CORN_FLAKES, CORN_FLAKES, VASELINE])
        assert stats["chunks_built"] == 2

    def test_duplicates_skipped_is_accurate(self):
        _, stats = build_chunks([CORN_FLAKES, CORN_FLAKES, CORN_FLAKES])
        assert stats["duplicates_skipped"] == 2

    def test_empty_list_produces_zero_stats(self):
        _, stats = build_chunks([])
        assert stats["chunks_built"] == 0
        assert stats["duplicates_skipped"] == 0
        assert stats["total_entries_processed"] == 0
        assert stats["null_nafdac_chunks"] == 0

    def test_subcategory_breakdown_all_categories(self):
        """All five subcategories represented across fixtures."""
        entries = [CORN_FLAKES, VASELINE, LIPTON, DANGOTE,
                   make_entry(nafdac_no="X1-0001", nafdac_no_clean="X1-0001",
                               product_name="TEST SPICE", product_name_upper="TEST SPICE",
                               subcategory="Salts, Spices, Soups, Sauces, Salads and Seasoning",
                               subcategory_lower="salts, spices, soups, sauces, salads and seasoning",
                               )]
        _, stats = build_chunks(entries)
        bd = stats["subcategory_breakdown"]
        assert bd["Cereals and Cereal Products"] == 1
        assert bd["Cosmetics"] == 1
        assert bd["Beverages"] == 1
        assert bd["Sweeteners"] == 1
        assert bd["Salts, Spices, Soups, Sauces, Salads and Seasoning"] == 1

    def test_null_nafdac_chunks_count_is_accurate(self):
        no_nafdac = make_entry(nafdac_no="", nafdac_no_clean="",
                               product_name="NO NAFDAC PRODUCT",
                               product_name_upper="NO NAFDAC PRODUCT")
        _, stats = build_chunks([no_nafdac, CORN_FLAKES])
        assert stats["null_nafdac_chunks"] == 1

    def test_stats_total_equals_chunks_plus_duplicates(self):
        """total_entries_processed == chunks_built + duplicates_skipped."""
        _, stats = build_chunks([CORN_FLAKES, CORN_FLAKES, VASELINE])
        assert stats["total_entries_processed"] == (
            stats["chunks_built"] + stats["duplicates_skipped"]
        )

    def test_different_product_same_nafdac_not_duplicate(self):
        """Same NAFDAC number but different product_name → two distinct chunks."""
        variant = make_entry(
            product_name="KELLOGG'S VARIANT",
            product_name_upper="KELLOGG'S VARIANT",
        )
        _, stats = build_chunks([CORN_FLAKES, variant])
        assert stats["chunks_built"] == 2
        assert stats["duplicates_skipped"] == 0


# ── GROUP G: ProductChunk model_dump() ────────────────────────────────────────

class TestProductChunkModelDump:
    """model_dump() must produce a plain dict with all fields for JSON serialisation."""

    def _chunk(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        return chunks[0]

    def test_model_dump_returns_dict(self):
        assert isinstance(self._chunk().model_dump(), dict)

    def test_model_dump_has_chunk_id(self):
        d = self._chunk().model_dump()
        assert "chunk_id" in d

    def test_model_dump_has_text(self):
        d = self._chunk().model_dump()
        assert "text" in d
        assert len(d["text"]) > 20

    def test_model_dump_has_metadata(self):
        d = self._chunk().model_dump()
        assert "metadata" in d
        assert isinstance(d["metadata"], dict)

    def test_model_dump_has_subcategory(self):
        d = self._chunk().model_dump()
        assert "subcategory" in d

    def test_model_dump_has_nafdac_no_clean(self):
        d = self._chunk().model_dump()
        assert "nafdac_no_clean" in d

    def test_model_dump_has_expiry_date_iso(self):
        d = self._chunk().model_dump()
        assert "expiry_date_iso" in d

    def test_model_dump_is_json_serialisable(self):
        """Must not raise when passed through json.dumps()."""
        d = self._chunk().model_dump()
        serialised = json.dumps(d)
        assert len(serialised) > 0

    def test_model_dump_chunk_id_matches_direct_attribute(self):
        chunk = self._chunk()
        assert chunk.model_dump()["chunk_id"] == chunk.chunk_id


# ── GROUP H: save_chunks() JSON File Contract ─────────────────────────────────

class TestSaveChunksContract:
    """save_chunks() must write valid, correctly-structured JSON."""

    def test_output_is_valid_json(self):
        chunks, _ = build_chunks([CORN_FLAKES, VASELINE])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "chunks.json")
            save_chunks(chunks, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_each_record_has_required_keys(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "chunks.json")
            save_chunks(chunks, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        record = data[0]
        for key in ["chunk_id", "text", "metadata", "subcategory",
                    "nafdac_no_clean", "expiry_date_iso"]:
            assert key in record, f"Missing key in saved JSON: {key!r}"

    def test_chunk_id_in_json_matches_in_memory_id(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "chunks.json")
            save_chunks(chunks, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        assert data[0]["chunk_id"] == chunks[0].chunk_id

    def test_parent_directories_created_automatically(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        with tempfile.TemporaryDirectory() as td:
            deep_path = os.path.join(td, "a", "b", "c", "d", "chunks.json")
            save_chunks(chunks, deep_path)
            assert os.path.exists(deep_path)

    def test_file_is_utf8_encoded(self):
        """Unicode product names must not be mangled in the output file."""
        unicode_entry = make_entry(
            nafdac_no="A8-0001", nafdac_no_clean="A8-0001",
            product_name="Produit Spécial",
            product_name_upper="PRODUIT SPÉCIAL",
        )
        chunks, _ = build_chunks([unicode_entry])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "chunks.json")
            save_chunks(chunks, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
        # ensure_ascii=False means the é is written as-is, not as \\u00e9
        assert "Spécial" in content or "Sp\\u00e9cial" in content  # either is valid JSON

    def test_empty_chunks_list_writes_empty_array(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "empty.json")
            save_chunks([], path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        assert data == []


# ── GROUP I: NAFDACEntry Schema Contract ──────────────────────────────────────

class TestNAFDACEntrySchema:
    """Schema contracts — field names, types, and valid subcategories."""

    def test_entry_creation_with_all_fields(self):
        """NAFDACEntry must be constructible with all 12 fields."""
        entry = make_entry()
        assert entry.nafdac_no == "A8-4114"
        assert entry.nafdac_no_clean == "A8-4114"
        assert entry.product_name == "KELLOGG'S CORN FLAKES"
        assert entry.product_name_upper == "KELLOGG'S CORN FLAKES"

    def test_all_valid_subcategories_accepted(self):
        """VALID_SUBCATEGORIES contains exactly the six real-data values + Unknown."""
        expected = {
            "Cereals and Cereal Products",
            "Cosmetics",
            "Fats and oils, and Fat Emulsions",
            "Salts, Spices, Soups, Sauces, Salads and Seasoning",
            "Beverages",
            "Sweeteners",
            "Unknown",
        }
        assert expected == VALID_SUBCATEGORIES

    def test_subcategory_lower_field_exists(self):
        """subcategory_lower is a required field (added to fix earlier test failures)."""
        entry = make_entry(subcategory_lower="cereals and cereal products")
        assert entry.subcategory_lower == "cereals and cereal products"

    def test_product_chunk_chunk_id_is_string(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        assert isinstance(chunks[0].chunk_id, str)

    def test_product_chunk_text_is_string(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        assert isinstance(chunks[0].text, str)

    def test_product_chunk_metadata_is_dict(self):
        chunks, _ = build_chunks([CORN_FLAKES])
        assert isinstance(chunks[0].metadata, dict)


# ── GROUP J: Null/Missing/Empty Input Handling ────────────────────────────────

class TestNullEmptyInputHandling:
    """Normalizer and chunk builder must handle sparse/empty data gracefully."""

    def test_normalizer_handles_integer_input(self):
        """Some Excel cells may be read as floats (e.g. NaN as float)."""
        # The function coerces to str first — 1234 becomes "1234" → no valid pattern
        result = normalize_nafdac_no(1234)
        # "1234" has no hyphen → no canonical match → None
        assert result is None

    def test_normalizer_handles_float_nan_as_string(self):
        """pandas reads empty cells as float NaN → str(nan) = 'nan' → null sentinel."""
        result = normalize_nafdac_no("nan")
        assert result is None

    def test_build_text_handles_missing_expiry_date(self):
        """If expiry_date_iso is empty string, 'Expiry Date:' is omitted from text."""
        no_expiry = make_entry(expiry_date_iso="")
        text = _build_text(no_expiry)
        assert "Expiry Date:" not in text

    def test_build_chunks_returns_empty_for_empty_input(self):
        chunks, stats = build_chunks([])
        assert chunks == []
        assert stats["chunks_built"] == 0

    def test_chunk_with_null_nafdac_has_empty_nafdac_clean(self):
        """A chunk built from an entry with no NAFDAC has nafdac_no_clean = ''."""
        no_nafdac = make_entry(nafdac_no="", nafdac_no_clean="",
                               product_name="GHOST PRODUCT",
                               product_name_upper="GHOST PRODUCT")
        chunks, _ = build_chunks([no_nafdac])
        assert chunks[0].nafdac_no_clean == ""

    def test_two_entries_same_no_nafdac_different_names_both_built(self):
        """Different products with empty NAFDAC must each get a unique chunk_id."""
        ghost1 = make_entry(nafdac_no="", nafdac_no_clean="",
                             product_name="GHOST A", product_name_upper="GHOST A")
        ghost2 = make_entry(nafdac_no="", nafdac_no_clean="",
                             product_name="GHOST B", product_name_upper="GHOST B")
        chunks, stats = build_chunks([ghost1, ghost2])
        assert stats["chunks_built"] == 2
        assert chunks[0].chunk_id != chunks[1].chunk_id

    def test_whitespace_only_presentation_treated_as_empty(self):
        """A presentation that is only whitespace must not emit 'Presentation:' label."""
        ws_entry = make_entry(presentation="   ")
        text = _build_text(ws_entry)
        assert "Presentation:" not in text
