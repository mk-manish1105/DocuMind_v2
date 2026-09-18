"""
Free OCR fallback for scanned/image-only PDF pages.

Uses the OCR.space free API (https://ocr.space/ocrapi) instead of
a local Tesseract install, since Render's native Python runtime
has no system package access.

This is called ONLY for pages where PyMuPDF's normal text
extraction returned nothing — i.e. pages that are scanned images
rather than real text.
"""

import logging
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def ocr_page_image(
    image_bytes: bytes,
) -> Optional[str]:
    """
    Send a single rendered page image to OCR.space and return
    the extracted text.

    Returns None if OCR is not configured, or if the request
    fails for any reason. Callers should treat None the same
    as "no text available" and continue gracefully.
    """

    if not settings.OCR_SPACE_API_KEY:

        logger.warning(
            "OCR_SPACE_API_KEY is not configured. "
            "Skipping OCR for scanned page."
        )

        return None

    try:

        response = requests.post(
            settings.OCR_SPACE_API_URL,
            files={
                "file": (
                    "page.png",
                    image_bytes,
                    "image/png",
                ),
            },
            data={
                "apikey": settings.OCR_SPACE_API_KEY,
                "language": "eng",
                "OCREngine": 2,
                "scale": "true",
                "isTable": "false",
            },
            timeout=60,
        )

        if response.status_code != 200:

            logger.error(
                "OCR.space API error %s: %s",
                response.status_code,
                response.text[:500],
            )

            return None

        data = response.json()

        if data.get("IsErroredOnProcessing"):

            logger.error(
                "OCR.space processing error: %s",
                data.get("ErrorMessage"),
            )

            return None

        results = data.get("ParsedResults") or []

        if not results:
            return None

        text = (
            results[0].get("ParsedText") or ""
        ).strip()

        return text or None

    except requests.exceptions.Timeout:

        logger.warning(
            "OCR.space request timed out."
        )

        return None

    except Exception:

        logger.exception(
            "OCR.space request failed."
        )

        return None