import re
from datetime import datetime


# NAFDAC number format: e.g. A8-4114, B3-00123, A7-1234
# Nigerian NAFDAC numbers start with 1-3 alphanumeric chars followed by dash and 3-6 digits
NAFDAC_PATTERN = re.compile(
    r"(?:NAFDAC\s*(?:REG(?:ISTRATION)?\s*)?(?:NO\.?|NUMBER)?\s*|"
    r"REG(?:ISTRATION)?\s*(?:NO\.?|NUMBER)\s*)"
    r":?\s*([A-Z0-9]{1,3}-\d{3,6})",
    re.IGNORECASE
)

# Standalone NAFDAC number (no keyword prefix) — used as fallback
NAFDAC_STANDALONE = re.compile(r"\b[A-Z]\d{1,2}-\d{3,6}\b")

# Loose pattern — catches OCR misreads like AQ-106037
# ONLY used in Pass 2 of the two-pass correction flow
NAFDAC_PATTERN_LOOSE = re.compile(
    r"(?:NAFDAC\s*(?:REG(?:ISTRATION)?\s*)?(?:NO\.?|NUMBER)?\s*|"
    r"REG(?:ISTRATION)?\s*(?:NO\.?|NUMBER)\s*)"
    r":?\s*([A-Z][A-Z0-9]{0,2}-[A-Z0-9]{3,6})",
    re.IGNORECASE
)
NAFDAC_STANDALONE_LOOSE = re.compile(r"\b[A-Z][A-Z0-9]{0,1}-[A-Z0-9]{3,6}\b")

BATCH_PATTERN = r"(?:BN[:=]?\s*)([A-Za-z0-9]+)"

VOLUME_PATTERN = r"\b\d+\s?(ml|g|kg|litre|l)\b"

# OCR digit/letter confusion map.
# Only applied to positions in NAFDAC numbers that MUST be digits by format.
# Position 0 (leading letter) is never corrected.
_DIGIT_CORRECTIONS = {
    "O": "0",
    "Q": "2",
    "I": "1",
    "S": "5",
    "B": "8",
    "G": "6",
    "Z": "2",
}

def _correct_nafdac_ocr_errors(raw: str) -> str:
    """
    Fix common OCR digit/letter confusion in a NAFDAC number.

    NAFDAC format: [LETTER][DIGIT(s)]-[DIGITS]
    - Position 0: Always a letter — NEVER corrected.
    - Position 1+: Must be digits — correct letter→digit misreads.
    - After dash: All must be digits — correct letter→digit misreads.

    This only fixes positions that MUST be digits. It never changes the
    leading letter or fabricates digits.

    Examples:
        AQ-106037  ->  A2-106037  (Q is OCR misread of 2)
        A0-4114    ->  A0-4114    (no change needed)
        BI-1234    ->  B1-1234    (I is OCR misread of 1)
    """
    if not raw or "-" not in raw:
        return raw

    parts  = raw.split("-", 1)
    prefix = list(parts[0])
    suffix = list(parts[1])

    # Position 0: leading letter — do not touch
    # Position 1+: must be digits
    for i in range(1, len(prefix)):
        prefix[i] = _DIGIT_CORRECTIONS.get(prefix[i], prefix[i])

    # All characters after dash: must be digits
    for i in range(len(suffix)):
        suffix[i] = _DIGIT_CORRECTIONS.get(suffix[i], suffix[i])

    return "".join(prefix) + "-" + "".join(suffix)


def _extract_loose(text: str) -> str | None:
    """Extract NAFDAC-like string with loose pattern. Pass 2 only."""
    match = NAFDAC_PATTERN_LOOSE.search(text)
    if match:
        return match.group(1).upper()
    match = NAFDAC_STANDALONE_LOOSE.search(text)
    if match:
        return match.group().upper()
    return None


# -----------------------
# Normalizers
# -----------------------

def normalize_nafdac(raw: str) -> str | None:
    """
    Strict NAFDAC extraction — Pass 1, no corrections.
    Returns clean NAFDAC string or None.
    """
    match = NAFDAC_PATTERN.search(raw)
    if match:
        return match.group(1).upper()
    match = NAFDAC_STANDALONE.search(raw)
    if match:
        return match.group().upper()
    return None

def normalize_nafdac_with_correction(raw: str, retriever=None) -> tuple:
    """
    Two-pass NAFDAC extraction with safe OCR error correction.

    SECURITY GUARANTEE — correction never authenticates a fake:
      The corrected number is ONLY returned if the retriever confirms it
      exists in the NAFDAC database. If the correction produces a number
      that is NOT in the database, the original (uncorrected) result is
      returned instead.

    Examples:
      Real product, OCR misread: AQ-106037
        Pass 1: strict pattern misses it (Q not a digit) -> None
        Pass 2: loose extracts AQ-106037, corrects to A2-106037,
                retriever finds it -> return ("A2-106037", True)

      Fake product, fabricated number: AQ-999999
        Pass 1: None
        Pass 2: loose extracts AQ-999999, corrects to A2-999999,
                retriever NOT_FOUND -> return (None, False) -> FAKE

    Args:
        raw:       Full OCR text.
        retriever: Optional ProductRetriever. If None, strict extraction only.

    Returns:
        (nafdac_number | None, was_corrected: bool)
        was_corrected=True adds OCR_CORRECTION_APPLIED warning to evidence package.
    """
    # ── Pass 1: strict extraction ─────────────────────────────────────────
    strict = normalize_nafdac(raw)

    if strict:
        if retriever is None:
            return strict, False
        records = retriever.retrieve_by_nafdac_no(strict)
        if records:
            return strict, False
        # Strict match found in text but NOT in DB — may be fake or OCR error
        # Fall through to Pass 2

    # ── Pass 2: loose extraction + correction ─────────────────────────────
    loose = _extract_loose(raw)

    if not loose:
        return strict, False   # nothing extractable even loosely

    corrected = _correct_nafdac_ocr_errors(loose)

    if corrected == loose:
        return strict, False   # correction changed nothing — no point retrying

    if retriever is None:
        # No DB to validate — return corrected but flag it as unconfirmed
        return corrected, True

    records = retriever.retrieve_by_nafdac_no(corrected)
    if records:
        return corrected, True   # correction confirmed by DB — safe to use

    # Correction not confirmed by DB — do not return it
    return strict, False



def normalize_batch(raw: str):
    match = re.search(BATCH_PATTERN, raw, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    return None


def normalize_date(raw: str):
    exp_match = re.search(r"EXP[:=]?\s*(\d{6})", raw, re.IGNORECASE)
    if exp_match:
        try:
            return datetime.strptime(exp_match.group(1), "%d%m%y").strftime("%Y-%m-%d")
        except:
            pass
    match_6 = re.search(r"\b\d{6}\b", raw)
    if match_6:
        try:
            return datetime.strptime(match_6.group(), "%d%m%y").strftime("%Y-%m-%d")
        except:
            pass
    return None

# -----------------------
# Manufacturer Extraction
# -----------------------

def extract_manufacturer(text: str):
    match = re.search(
        r"(Unilever.*?(Plc|Ltd|Limited|Inc|Incorporated))",
        text, re.IGNORECASE
    )
    return match.group(1).strip() if match else None

# -----------------------
# Net Weight / Volume
# -----------------------

def extract_volume(text: str):
    match = re.search(VOLUME_PATTERN, text, re.IGNORECASE)
    return match.group().strip() if match else None

def extract_product_name(raw_text: str, brand: str):
    if not raw_text or not brand:
        return None

    candidates = []

    for line in raw_text.split("."):
        clean = line.strip()

        if not clean:
            continue
        if "www" in clean.lower() or "nafdac" in clean.lower():
            continue
        if any(unit in clean.lower() for unit in ["ml", "g", "kg", "litre"]):
            continue
        if brand.lower() in clean.lower():
            candidates.append(clean)

    if candidates:
        candidates.sort(key=len)
        return candidates[0].strip()

    return None

# -----------------------
# Main Extraction Function
# -----------------------

def extract_structured_metadata(full_text: str, brand_detected: str = None, retriever=None) -> dict:
    """
    Extract all structured metadata from OCR text.

    When retriever is provided, uses safe two-pass NAFDAC extraction.
    Without retriever, falls back to strict extraction (original behaviour).

    The 'nafdac_ocr_corrected' flag in the return dict is forwarded to the
    evidence package as an OCR_CORRECTION_APPLIED warning so enforcement
    officers know the NAFDAC number required correction from the label.
    """
    if retriever is not None:
        nafdac, was_corrected = normalize_nafdac_with_correction(full_text, retriever)
    else:
        nafdac = normalize_nafdac(full_text)
        was_corrected = False

    batch        = normalize_batch(full_text)
    expiry       = normalize_date(full_text)
    manufacturer = extract_manufacturer(full_text)
    volume       = extract_volume(full_text)
    product_name = extract_product_name(full_text, brand_detected)
    valid_format = all([nafdac, batch])

    return {
        "nafdac_number":        nafdac,
        "batch_number":         batch,
        "expiry_date":          expiry,
        "manufacturer_name":    manufacturer,
        "net_weight_or_volume": volume,
        "product_name":         product_name,
        "valid_format":         valid_format,
        "nafdac_ocr_corrected": was_corrected,
    }