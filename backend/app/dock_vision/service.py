import logging

import cv2
import numpy as np
from pyzbar.pyzbar import decode as zbar_decode

logger = logging.getLogger(__name__)


class QrDecodeError(Exception):
    """Raised when no QR code can be extracted from the given image bytes."""


def decode_qr_from_image_bytes(image_bytes: bytes) -> str:
    """Decode a single QR code from raw JPEG/PNG bytes.

    Converts straight to grayscale before detection — same optimization
    validated in the standalone OpenCV/pyzbar client this replaces
    (2x faster than scanning 3-channel color data, no accuracy loss for QR).

    Raises QrDecodeError if the image can't be parsed or contains no QR code.
    Returns the first decoded QR payload only — a ride token QR is the only
    thing dock hardware should ever see in frame.
    """
    if not image_bytes:
        raise QrDecodeError("Empty image payload.")

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise QrDecodeError("Could not decode image bytes (not a valid JPEG/PNG).")

    results = zbar_decode(img)
    if not results:
        raise QrDecodeError("No QR code detected in image.")

    payload = results[0].data.decode("utf-8")
    if not payload:
        raise QrDecodeError("QR code detected but payload was empty.")

    return payload