"""
Image upload utility — uploads base64 images to Google Cloud Storage.
Returns a public GCS URL or None if upload fails.

GCS key structure:
  scans/{8-char-prefix}/{unix_timestamp}_{random}.jpg   — scan images
  products/{product_id}/master.jpg                      — product master artwork

The GCS bucket (GCS_BUCKET) must have uniform bucket-level access with the
`allUsers:objectViewer` IAM binding so stored URLs are permanently accessible
by the AI pipeline and the dashboard without expiry.

AI PDF reports use a separate private bucket (GCS_REPORTS_BUCKET) with
signed URLs — see backend/admin/n8n_client.py for that flow.
"""
import base64
import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger("image_upload")

# Magic-byte → MIME type mapping for content-type detection
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG",      "image/png"),
    (b"RIFF",         "image/webp"),
    (b"GIF8",         "image/gif"),
]


def _detect_content_type(raw: bytes) -> str:
    for sig, ct in _SIGNATURES:
        if raw[: len(sig)] == sig:
            return ct
    return "image/jpeg"


def _gcs_client():
    """Return a configured GCS client using Application Default Credentials."""
    from google.cloud import storage
    return storage.Client()


def upload_scan_image(
    image_data: str,
    folder: str = "scans",
    scan_id: Optional[str] = None,
) -> Optional[str]:
    """
    Upload a base64 data-URL image to GCS.

    Args:
        image_data: base64 data-URL (e.g. 'data:image/jpeg;base64,...')
                    or raw base64 string without the prefix.
        folder:     GCS key prefix — 'scans' for scan images, 'products' for
                    product artwork.
        scan_id:    optional scan UUID; first 8 chars used as path component
                    to group images from the same scan. Random prefix used if None.

    Returns:
        Public GCS URL:
          https://storage.googleapis.com/{GCS_BUCKET}/{key}
        or None if upload fails or GCS credentials are not configured.

    Called from consumer.py via run_in_executor (sync-safe, no event loop used).
    """
    if not image_data:
        return None

    from backend.config import settings

    if not settings.GCS_BUCKET:
        logger.debug("GCS not configured — skipping image upload")
        return None

    try:
        # Strip data-URL prefix if present: "data:image/jpeg;base64,..."
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[-1]

        raw_bytes = base64.b64decode(image_data)
        content_type = _detect_content_type(raw_bytes)
        ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]

        prefix = str(scan_id)[:8] if scan_id else uuid.uuid4().hex[:8]
        key = f"{folder}/{prefix}/{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"

        bucket = _gcs_client().bucket(settings.GCS_BUCKET)
        blob = bucket.blob(key)
        blob.upload_from_string(raw_bytes, content_type=content_type)

        url = f"https://storage.googleapis.com/{settings.GCS_BUCKET}/{key}"
        logger.info("Image uploaded to GCS: %s", url)
        return url

    except Exception as exc:
        logger.warning("GCS upload failed: %s", exc)
        return None
