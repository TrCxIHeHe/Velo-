"""Synthetic ESP32-CAM-like frames for decoder / scan-endpoint tests.

Renders a QR into a 320x240 grayscale canvas (QVGA, like the OV2640 config in
the firmware), optionally off-centre / smaller / in perspective, adds sensor
noise and JPEG-compresses it.  `qrcode` is a dev-only dependency.
"""
import uuid
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import qrcode
from jose import jwt

from app.config import settings

W, H = 320, 240


def make_ride_jwt(dock_id, *, ttl_seconds=30, user_id=None) -> str:
    """A ride JWT shaped exactly like RideService issues (≈330 chars)."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id or uuid.uuid4()),
            "dock_id": str(dock_id),
            "type": "ride",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=ttl_seconds),
        },
        settings.RIDE_TOKEN_SECRET,
        algorithm=settings.RIDE_TOKEN_ALGORITHM,
    )


def qr_matrix(data: str) -> np.ndarray:
    # Error-correction M = qr_flutter's default, i.e. what the app renders.
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    return np.array(qr.make_image().convert("L"))


def frame_with_qr(
    data: str, *, side=200, cx=160, cy=120, persp=0.0, bg=170, noise=6, quality=85, seed=0
) -> bytes:
    rng = np.random.default_rng(seed)
    qr = cv2.resize(qr_matrix(data), (side, side), interpolation=cv2.INTER_AREA)
    src = np.float32([[0, 0], [side, 0], [side, side], [0, side]])
    d = persp * side
    dst = np.float32(
        [
            [cx - side / 2 + d, cy - side / 2 + d * 0.4],
            [cx + side / 2 - d, cy - side / 2],
            [cx + side / 2 - d * 0.3, cy + side / 2 - d],
            [cx - side / 2, cy + side / 2],
        ]
    )
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(qr, m, (W, H), borderValue=bg)
    mask = cv2.warpPerspective(np.full_like(qr, 255), m, (W, H))
    img = np.where(mask > 0, warped, np.full((H, W), bg, np.uint8)).astype(np.float32)
    img = np.clip(img + rng.normal(0, noise, img.shape), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(
        ".jpg", cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    assert ok
    return enc.tobytes()


def frame_without_qr(seed=1) -> bytes:
    rng = np.random.default_rng(seed)
    img = np.clip(128 + rng.normal(0, 25, (H, W, 3)), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    assert ok
    return enc.tobytes()
