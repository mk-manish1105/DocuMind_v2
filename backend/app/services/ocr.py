"""
Free OCR fallback for scanned/image-only PDF pages.

Uses the OCR.space free API (https://ocr.space/ocrapi) instead of
a local Tesseract install, since Render's native Python runtime
has no system package access.

This is called ONLY for pages where PyMuPDF's normal text
extraction returned nothing — i.e. pages that are scanned images
rather than real text.
"""

import io
import logging
from typing import Optional, Tuple

import requests
from PIL import Image, ImageOps

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# OCR.SPACE FILE-SIZE LIMIT
#
# The FREE OCR.space key rejects any file larger than 1 MB.
# Phone photos and screenshots are usually bigger than that,
# so every image is shrunk below this limit before upload.
# ============================================================

OCR_MAX_BYTES = 900 * 1024

OCR_MAX_DIMENSION = 2600

_OCR_NATIVE_TYPES = {
    "image/png",
    "image/jpeg",
}


def _prepare_image_for_ocr(
    image_bytes: bytes,
    filename: str,
    content_type: str,
) -> Tuple[bytes, str, str]:
    """
    Make sure an image is something OCR.space will accept.

    - PNG / JPEG under the size limit are sent untouched.
    - WEBP (not supported by OCR.space) is converted to JPEG.
    - Large images are downscaled and re-encoded as JPEG
      until they fit under OCR_MAX_BYTES.
    - Phone-camera rotation (EXIF) is applied so the text
      is upright for OCR.
    """

    try:

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        detected_type = {
            "PNG": "image/png",
            "JPEG": "image/jpeg",
        }.get(image.format or "")

        if (
            detected_type in _OCR_NATIVE_TYPES
            and len(image_bytes) <= OCR_MAX_BYTES
        ):
            return (
                image_bytes,
                filename,
                detected_type,
            )

        image = ImageOps.exif_transpose(
            image
        )

        if image.mode in ("RGBA", "LA", "P"):

            image = image.convert("RGBA")

            background = Image.new(
                "RGB",
                image.size,
                (255, 255, 255),
            )

            background.paste(
                image,
                mask=image.split()[-1],
            )

            image = background

        else:

            image = image.convert("RGB")

        longest_side = max(image.size)

        if longest_side > OCR_MAX_DIMENSION:

            scale = OCR_MAX_DIMENSION / longest_side

            image = image.resize(
                (
                    max(1, int(image.width * scale)),
                    max(1, int(image.height * scale)),
                ),
                Image.LANCZOS,
            )

        output = image_bytes

        for _ in range(8):

            for quality in (85, 75, 65, 55):

                buffer = io.BytesIO()

                image.save(
                    buffer,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )

                output = buffer.getvalue()

                if len(output) <= OCR_MAX_BYTES:

                    logger.info(
                        "Prepared image for OCR: "
                        "%d -> %d bytes",
                        len(image_bytes),
                        len(output),
                    )

                    return (
                        output,
                        "image.jpg",
                        "image/jpeg",
                    )

            image = image.resize(
                (
                    max(1, int(image.width * 0.8)),
                    max(1, int(image.height * 0.8)),
                ),
                Image.LANCZOS,
            )

        return output, "image.jpg", "image/jpeg"

    except Exception:

        logger.exception(
            "Could not prepare image for OCR. "
            "Sending the original bytes."
        )

        return image_bytes, filename, content_type


def ocr_image_bytes(
    image_bytes: bytes,
    filename: str = "page.png",
    content_type: str = "image/png",
) -> Optional[str]:
    """
    Send a single image (a rendered PDF page, or a directly
    uploaded image such as a screenshot) to OCR.space and
    return the extracted text.

    Returns None if OCR is not configured, or if the request
    fails for any reason. Callers should treat None the same
    as "no text available" and continue gracefully.
    """

    if not settings.OCR_SPACE_API_KEY:

        logger.warning(
            "OCR_SPACE_API_KEY is not configured. "
            "Skipping OCR for image."
        )

        return None

    try:

        image_bytes, filename, content_type = (
            _prepare_image_for_ocr(
                image_bytes,
                filename,
                content_type,
            )
        )

        response = requests.post(
            settings.OCR_SPACE_API_URL,
            files={
                "file": (
                    filename,
                    image_bytes,
                    content_type,
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


def ocr_page_image(
    image_bytes: bytes,
) -> Optional[str]:
    """
    Backward-compatible wrapper for rendered PDF pages
    (always PNG). Use ocr_image_bytes() directly for
    anything else, such as a directly uploaded image.
    """

    return ocr_image_bytes(
        image_bytes,
        filename="page.png",
        content_type="image/png",
    )