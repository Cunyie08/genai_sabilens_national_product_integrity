"""
File upload utility — uploads FastAPI UploadFile objects to Google Cloud Storage.
Used for multipart/form-data uploads (e.g. product artwork, documents).

For base64 scan image uploads from the consumer app see image_upload.py.
"""
import logging
import uuid
from typing import Optional

from fastapi import UploadFile

logger = logging.getLogger("file_upload")


def _gcs_client():
    from google.cloud import storage
    return storage.Client()


async def upload_file(
    file: UploadFile,
    folder: str = "uploads",
) -> Optional[str]:
    """
    Upload a FastAPI UploadFile to GCS.

    Returns public GCS URL or None if upload fails / GCS not configured.
    """
    from backend.config import settings

    if not settings.GCS_BUCKET:
        logger.debug("GCS not configured — skipping file upload")
        return None

    try:
        content = await file.read()
        ext = ""
        if file.filename and "." in file.filename:
            ext = "." + file.filename.rsplit(".", 1)[-1].lower()

        key = f"{folder}/{uuid.uuid4().hex}{ext}"
        content_type = file.content_type or "application/octet-stream"

        bucket = _gcs_client().bucket(settings.GCS_BUCKET)
        blob = bucket.blob(key)
        blob.upload_from_string(content, content_type=content_type)

        url = f"https://storage.googleapis.com/{settings.GCS_BUCKET}/{key}"
        logger.info("File uploaded to GCS: %s", url)
        return url

    except Exception as exc:
        logger.warning("GCS file upload failed: %s", exc)
        return None


async def upload_multiple(
    files: list[UploadFile],
    folder: str = "uploads",
) -> list[str]:
    """Upload multiple files, returning a list of URLs (skipping failed uploads)."""
    urls = []
    for file in files:
        url = await upload_file(file, folder)
        if url:
            urls.append(url)
    return urls
