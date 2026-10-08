"""
dock_vision/service.py — QR decode pipeline for ESP32-CAM JPEG frames.

Baseline (the standalone ESP32-CAM test that worked well):

    frame = cv2.imdecode(...)
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pyzbar.decode(gray)

Strategy order — cheapest first, the expensive fallbacks only run if the fast
path finds nothing.  EVERY strategy scans the WHOLE image: nothing assumes the
QR sits at a particular position in the 320x240 frame.

  fast path
    1. pyzbar-gray                   pyzbar on the raw grayscale frame
    2. opencv-qrdetector             cv2.QRCodeDetector on the same frame
  fallbacks (each variant is tried with pyzbar, then OpenCV)
    3. opencv-aruco-qrdetector       cv2.QRCodeDetectorAruco (OpenCV >= 4.8)
    4. upscale2x                     INTER_CUBIC x2 — gives dense QRs more px/module
    5. clahe                         local contrast equalisation (on the 2x image)
    6. otsu                          global threshold (on the 2x image)
    7. adaptive                      adaptive threshold (on the 2x image)
    8. upscale3x                     INTER_CUBIC x3
    9. perspective                   locate the QR quadrilateral, warp it to a
                                     fronto-parallel square, decode again

A QR that cannot be decoded raises QrDecodeError (→ DOCK_SCAN_QR_NOT_FOUND).
Whatever the QR *contains* (valid / expired / wrong dock JWT) is decided later
by the ride service — this module never looks inside the payload, and never
logs it (the payload is a ride JWT).
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# pyzbar needs the system zbar library (Ubuntu: apt install libzbar0;
# Windows: bundled DLLs + vcredist_x64).  Degrade gracefully if absent.
try:
    from pyzbar.pyzbar import ZBarSymbol
    from pyzbar.pyzbar import decode as _pyzbar_decode

    _PYZBAR_AVAILABLE = True
except (ImportError, OSError):  # pragma: no cover - environment dependent
    _PYZBAR_AVAILABLE = False
    logger.warning(
        "pyzbar / libzbar not available — decoding with OpenCV only. "
        "Install: pip install pyzbar  (Ubuntu: apt install libzbar0)"
    )

MIN_IMAGE_BYTES = 1024


class QrDecodeError(Exception):
    """Raised when no QR code can be extracted from the given image bytes."""


# ─── Low-level decoders ──────────────────────────────────────────────────────

def _pyzbar(img: np.ndarray) -> Optional[str]:
    if not _PYZBAR_AVAILABLE:
        return None
    try:
        for obj in _pyzbar_decode(img, symbols=[ZBarSymbol.QRCODE]):
            try:
                text = obj.data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if text:
                return text
    except Exception as exc:  # zbar/numpy errors must never become a 500
        logger.warning("[QR] pyzbar raised %s", type(exc).__name__)
    return None


_ARUCO_AVAILABLE = hasattr(cv2, "QRCodeDetectorAruco")


def _opencv(img: np.ndarray) -> Optional[str]:
    try:
        text, _pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return text or None
    except cv2.error as exc:
        logger.warning("[QR] OpenCV QRCodeDetector raised %s", type(exc).__name__)
        return None


def _opencv_aruco(img: np.ndarray) -> Optional[str]:
    if not _ARUCO_AVAILABLE:
        return None
    try:
        text, _pts, _ = cv2.QRCodeDetectorAruco().detectAndDecode(img)
        return text or None
    except cv2.error as exc:
        logger.warning("[QR] OpenCV QRCodeDetectorAruco raised %s", type(exc).__name__)
        return None


# ─── Image variants (only built when a fallback needs them) ──────────────────

def _upscale(gray: np.ndarray, factor: int) -> np.ndarray:
    return cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def _clahe(gray: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)


def _otsu(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, out = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def _adaptive(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    # Block size scales with image size so it spans several QR modules.
    block = max(11, (min(gray.shape[:2]) // 16) | 1)
    return cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 5
    )


# ─── Perspective correction ──────────────────────────────────────────────────

def _order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype=np.float32,
    )


def _locate_quad(img: np.ndarray) -> Optional[np.ndarray]:
    """QR localisation: return the 4 corners of a QR found anywhere in img."""
    try:
        ok, pts = cv2.QRCodeDetector().detect(img)
    except cv2.error:
        return None
    if not ok or pts is None:
        return None
    quad = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
    if quad.shape != (4, 2):
        return None
    # Reject degenerate detections (tiny / collapsed quadrilaterals).
    if cv2.contourArea(quad) < 400:
        return None
    return _order_quad(quad)


def _perspective_variants(gray: np.ndarray):
    """
    Yield (name, rectified image) for every localisable QR.  The quad is found
    on the raw and on a 2x upscaled copy (small QRs are often only localised
    after upscaling), then warped to a fronto-parallel square with a quiet zone.
    """
    side, margin = 360, 40
    dst = np.array(
        [[margin, margin], [margin + side, margin],
         [margin + side, margin + side], [margin, margin + side]],
        dtype=np.float32,
    )
    size = side + 2 * margin
    up2 = _upscale(gray, 2)
    sources = (
        ("raw", gray),
        ("2x", up2),
        ("2x-adaptive", _adaptive(up2)),
        ("2x-otsu", _otsu(up2)),
    )
    seen: list[np.ndarray] = []
    for label, base in sources:
        quad = _locate_quad(base)
        if quad is None:
            continue
        # Skip duplicate localisations (same quad, normalised to raw pixels).
        scale = base.shape[1] / gray.shape[1]
        norm = quad / scale
        if any(np.abs(norm - prev).max() < 3 for prev in seen):
            continue
        seen.append(norm)
        # Warp from the *original-resolution* gray for fidelity, using the
        # quad found on whichever variant localised it.
        matrix = cv2.getPerspectiveTransform(norm.astype(np.float32), dst)
        warped = cv2.warpPerspective(
            gray, matrix, (size, size), flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        yield f"perspective[{label}]", warped
        yield f"perspective[{label}]+otsu", _otsu(warped)


# ─── Pipeline ────────────────────────────────────────────────────────────────

def _try(name: str, fn: Callable[[np.ndarray], Optional[str]], img: np.ndarray):
    text = fn(img)
    if text:
        logger.info("[QR] %s: decoded", name)
        return text
    logger.info("[QR] %s: no result", name)
    return None


def _variant_stages(gray: np.ndarray):
    """Lazily yield (name, image) so unused (costly) variants are never built."""
    up2 = _upscale(gray, 2)
    yield "upscale2x", up2
    yield "clahe", _clahe(up2)
    yield "otsu", _otsu(up2)
    yield "adaptive", _adaptive(up2)
    yield "upscale3x", _upscale(gray, 3)


def decode_qr_with_strategy(image_bytes: bytes) -> tuple[str, str]:
    """
    Decode one QR code from JPEG/PNG bytes.  Returns ``(payload, strategy)``.
    Raises QrDecodeError if nothing could be decoded.
    """
    if not image_bytes or len(image_bytes) < MIN_IMAGE_BYTES:
        raise QrDecodeError("Empty or too-small image payload (< 1 KB).")

    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise QrDecodeError("Could not decode image bytes — not a valid JPEG/PNG.")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    started = time.perf_counter()

    def done(text: str, strategy: str) -> tuple[str, str]:
        ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[QR] Decoder succeeded using: %s (%dx%d, payload %d chars, %.0f ms)",
            strategy, w, h, len(text), ms,
        )
        return text, strategy

    # ── Fast path ────────────────────────────────────────────────────────────
    if _PYZBAR_AVAILABLE:
        text = _try("pyzbar", _pyzbar, gray)
        if text:
            return done(text, "pyzbar-gray")

    text = _try("OpenCV QRCodeDetector", _opencv, gray)
    if text:
        return done(text, "opencv-qrdetector-gray")

    # ── Fallbacks ────────────────────────────────────────────────────────────
    text = _try("OpenCV QRCodeDetectorAruco", _opencv_aruco, gray)
    if text:
        return done(text, "opencv-aruco-qrdetector-gray")

    for name, variant in _variant_stages(gray):
        for suffix, fn in (("pyzbar", _pyzbar), ("opencv", _opencv)):
            if fn is _pyzbar and not _PYZBAR_AVAILABLE:
                continue
            text = _try(f"{name}+{suffix}", fn, variant)
            if text:
                return done(text, f"{name}-{suffix}")

    for name, warped in _perspective_variants(gray):
        for suffix, fn in (("pyzbar", _pyzbar), ("opencv", _opencv)):
            if fn is _pyzbar and not _PYZBAR_AVAILABLE:
                continue
            text = _try(f"{name}+{suffix}", fn, warped)
            if text:
                return done(text, f"{name}-{suffix}")

    ms = (time.perf_counter() - started) * 1000
    logger.info("[QR] No QR found in %dx%d frame after all strategies (%.0f ms)", w, h, ms)
    raise QrDecodeError("No QR code detected after all decode strategies.")


def decode_qr_from_image_bytes(image_bytes: bytes) -> str:
    """Backwards-compatible wrapper: returns only the decoded payload."""
    return decode_qr_with_strategy(image_bytes)[0]
