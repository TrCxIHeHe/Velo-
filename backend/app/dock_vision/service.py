"""
dock_vision/service.py — QR decode pipeline for ESP32-CAM JPEG frames.

Fixes applied (from audit B-01, B-02, B-11):
  - Image normalisation: resize to 640×480, GaussianBlur, adaptiveThreshold
  - pyzbar fallback after cv2 failures (far superior on compressed/blurry camera images)
  - Minimum image size guard
  - Resize normalisation for very large or very small frames
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# pyzbar is a significantly better decoder for real camera images.
# It handles rotated, blurry and JPEG-compressed QR codes much better than
# cv2.QRCodeDetector. Import it with a graceful fallback so the service
# still works if the system zbar library is missing (install: libzbar0 on Ubuntu).
try:
    from PIL import Image
    from pyzbar.pyzbar import decode as pyzbar_decode
    _PYZBAR_AVAILABLE = True
except (ImportError, OSError):
    _PYZBAR_AVAILABLE = False
    logger.warning(
        "pyzbar / Pillow not available — falling back to cv2-only decode. "
        "Run: pip install pyzbar Pillow   (Ubuntu: apt install libzbar0; Windows: install vcredist_x64)"
    )


class QrDecodeError(Exception):
    """Raised when no QR code can be extracted from the given image bytes."""


# ─── Image pre-processing ────────────────────────────────────────────────────

def _normalise_size(img: np.ndarray) -> np.ndarray:
    """
    Clamp the image to a width near 640 px — cv2.QRCodeDetector performs best
    there.  Very small images (QQVGA, 160×120) are too low-detail; very large
    ones (UXGA 1600×1200) are slow and add no QR readability benefit.

    Fix: B-11 / I-11
    """
    h, w = img.shape[:2]
    if w > 800:
        scale = 640.0 / w
        img = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_AREA)
    elif w < 200:
        img = cv2.resize(img, (640, 480), interpolation=cv2.INTER_LINEAR)
    return img


def _preprocess_for_qr(img: np.ndarray) -> np.ndarray:
    """
    Apply contrast normalisation so QR codes buried in phone-screen glare or
    uneven dock lighting are still detectable.

    Pipeline (B-01 / I-03):
      1. Resize to ~640 px wide
      2. GaussianBlur — removes JPEG compression noise (avoids false edges)
      3. adaptiveThreshold — normalises uneven illumination at the dock
    """
    img = _normalise_size(img)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )
    return img


# ─── Main decoder ────────────────────────────────────────────────────────────

def decode_qr_from_image_bytes(image_bytes: bytes) -> str:
    """
    Decode a single QR code from raw JPEG/PNG bytes sent by the ESP32-CAM.

    Decode strategy (three-pass, cheapest first):
      Pass 1 — cv2.QRCodeDetector on raw grayscale (fast, works for crisp images)
      Pass 2 — cv2.QRCodeDetector on pre-processed (normalised contrast)
      Pass 3 — pyzbar fallback (best on blurry/rotated/compressed frames)

    Raises QrDecodeError if no QR code is found after all passes.
    """
    if not image_bytes or len(image_bytes) < 1024:
        raise QrDecodeError("Empty or too-small image payload (< 1 KB).")

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise QrDecodeError(
            "Could not decode image bytes — not a valid JPEG/PNG."
        )

    # Normalise size for all passes
    img = _normalise_size(img)

    detector = cv2.QRCodeDetector()

    # ── Pass 1: cv2 on raw grayscale ──────────────────────────────────────────
    payload, _pts, _ = detector.detectAndDecode(img)
    if payload:
        logger.info("QR decoded via cv2 (raw grayscale)")
        return payload

    # ── Pass 2: cv2 on pre-processed image ────────────────────────────────────
    enhanced = _preprocess_for_qr(img.copy())
    payload, _pts, _ = detector.detectAndDecode(enhanced)
    if payload:
        logger.info("QR decoded via cv2 (adaptive-threshold enhanced)")
        return payload

    # ── Pass 3: pyzbar fallback ───────────────────────────────────────────────
    # B-02 / I-02 — pyzbar (ZBar library) is far superior for compressed,
    # rotated and low-contrast QR codes coming from camera frames.
    if _PYZBAR_AVAILABLE:
        pil_img = Image.fromarray(img)
        objects = pyzbar_decode(pil_img)
        if objects:
            result = objects[0].data.decode("utf-8")
            logger.info("QR decoded via pyzbar fallback")
            return result

        # Also try pyzbar on the enhanced image
        pil_enhanced = Image.fromarray(enhanced)
        objects = pyzbar_decode(pil_enhanced)
        if objects:
            result = objects[0].data.decode("utf-8")
            logger.info("QR decoded via pyzbar (enhanced image)")
            return result

    raise QrDecodeError(
        "No QR code detected after cv2 (raw + enhanced) and pyzbar passes."
    )
