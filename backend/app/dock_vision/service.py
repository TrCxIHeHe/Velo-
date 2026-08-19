import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class QrDecodeError(Exception):
    """Raised when no QR code can be extracted from the given image bytes."""


def decode_qr_from_image_bytes(image_bytes: bytes) -> str:
    """Decode a single QR code from raw JPEG/PNG bytes."""

    if not image_bytes:
        raise QrDecodeError("Empty image payload.")

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise QrDecodeError(
            "Could not decode image bytes (not a valid JPEG/PNG)."
        )

    detector = cv2.QRCodeDetector()

    payload, points, _ = detector.detectAndDecode(img)

    if not payload:
        raise QrDecodeError("No QR code detected.")

    return payload