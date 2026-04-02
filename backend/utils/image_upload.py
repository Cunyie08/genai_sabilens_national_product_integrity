"""
Image upload utility — uploads base64 images to Cloudinary.
Returns a public URL or None if upload fails.
"""
import base64
import logging
import re
from typing import Optional

logger = logging.getLogger("image_upload")


def _init_cloudinary():
    """Configure cloudinary from environment settings. Returns True if configured."""
    try:
        import cloudinary
        from backend.config import settings

        cloud_name = settings.CLOUDINARY_CLOUD_NAME
        api_key = settings.CLOUDINARY_API_KEY
        api_secret = settings.CLOUDINARY_API_SECRET

        # Also try parsing from CLOUDINARY_URL: cloudinary://api_key:api_secret@cloud_name
        if (not cloud_name or not api_key or not api_secret) and settings.CLOUDINARY_URL:
            match = re.match(
                r"cloudinary://([^:]+):([^@]+)@(.+)", settings.CLOUDINARY_URL
            )
            if match:
                api_key = api_key or match.group(1)
                api_secret = api_secret or match.group(2)
                cloud_name = cloud_name or match.group(3)

        if cloud_name and api_key and api_secret:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True,
            )
            return True
    except Exception as exc:
        logger.debug("Cloudinary init failed: %s", exc)
    return False


def upload_scan_image(image_data: str, folder: str = "sabilens/scans") -> Optional[str]:
    """
    Upload a base64 data-URL image to Cloudinary.

    Args:
        image_data: base64 data-URL (e.g. 'data:image/jpeg;base64,...')
        folder: Cloudinary folder path

    Returns:
        Public Cloudinary URL, or None if upload fails.
    """
    if not image_data:
        return None

    try:
        if not _init_cloudinary():
            logger.debug("Cloudinary not configured — skipping image upload")
            return None

        import cloudinary.uploader

        # Strip the data-URL prefix if present
        if image_data.startswith("data:"):
            # e.g. "data:image/jpeg;base64,/9j/..."
            image_data = image_data.split(",", 1)[-1]

        # Decode and re-encode to validate
        raw_bytes = base64.b64decode(image_data)

        result = cloudinary.uploader.upload(
            raw_bytes,
            folder=folder,
            resource_type="image",
            quality="auto",
            fetch_format="auto",
        )
        url = result.get("secure_url")
        logger.info("Image uploaded to Cloudinary: %s", url)
        return url

    except Exception as exc:
        logger.warning("Cloudinary upload failed: %s", exc)
        return None
