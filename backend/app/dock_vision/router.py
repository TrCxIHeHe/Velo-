"""
dock_vision/router.py — HTTP layer for ESP32-CAM QR scan endpoint.

Fixes applied (from audit B-03 through B-07):
  B-03: MAX_IMAGE_BYTES reduced from 5 MB → 200 KB (matches real OV2640 VGA frames)
  B-04: AuditLogRepository wired in — every scan attempt is logged
  B-05: Rate limiting added (@limiter.limit)
  B-06: Content-Type validation — rejects non-image bodies at the HTTP layer
  + MIN_IMAGE_BYTES guard — rejects obviously-invalid tiny payloads
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock_vision.service import QrDecodeError, decode_qr_from_image_bytes
from app.ride.router import RideServiceDep

router = APIRouter(prefix="/docks", tags=["dock-vision"])

# OV2640 at VGA (640×480) quality 12 produces ~40–80 KB frames.
# 200 KB is generous headroom; 5 MB (original) wastes malloc + numpy decode
# on any junk payload and is 60–250× larger than any real frame (B-03).
MAX_IMAGE_BYTES = 200 * 1024   # 200 KB
MIN_IMAGE_BYTES = 1_024        # < 1 KB is not a real camera frame


@router.post("/{dock_id}/scan")
@limiter.limit("20/minute")   # B-05: ESP32 scans at most ~4/min; 20 blocks DoS
async def scan_dock_image(
    dock_id: uuid.UUID,
    request: Request,
    service: RideServiceDep,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Accepts a raw JPEG body (Content-Type: image/jpeg) sent directly by the
    ESP32-CAM firmware — NOT multipart/form-data.

    Raw POST is intentional: multipart encoding would force the ESP32 to
    malloc a boundary-wrapped buffer, which raw POST avoids entirely.
    """
    # ── B-06: Content-Type guard ──────────────────────────────────────────────
    content_type = request.headers.get("content-type", "")
    if "image" not in content_type.lower():
        return error_response(
            "DOCK_SCAN_INVALID_CONTENT_TYPE",
            "Expected Content-Type: image/jpeg. "
            "Check ESP32 firmware — it must set the Content-Type header.",
            415,
        )

    image_bytes = await request.body()

    # ── Size guards ───────────────────────────────────────────────────────────
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return error_response(
            "DOCK_SCAN_IMAGE_TOO_LARGE",
            f"Image exceeds {MAX_IMAGE_BYTES // 1024} KB limit. "
            "Lower camera resolution/quality in firmware "
            "(FRAMESIZE_VGA, jpeg_quality=12 recommended).",
            413,
        )
    if len(image_bytes) < MIN_IMAGE_BYTES:
        return error_response(
            "DOCK_SCAN_IMAGE_TOO_SMALL",
            "Image too small to be a real camera frame (< 1 KB). "
            "Check the ESP32 capture loop — fb->len should be > 10 000 bytes.",
            422,
        )

    audit = AuditLogRepository(session)   # B-04: wire audit repo

    # ── QR decode ─────────────────────────────────────────────────────────────
    try:
        ride_token = decode_qr_from_image_bytes(image_bytes)
    except QrDecodeError as exc:
        # Log every failed scan so you can monitor false-scan rates in prod
        await audit.log(
            None, "DOCK_SCAN_FAIL", "dock", str(dock_id),
            meta=f"bytes={len(image_bytes)} reason={exc}",
        )
        return error_response("DOCK_SCAN_QR_NOT_FOUND", str(exc), 422)

    # ── Ride confirmation ──────────────────────────────────────────────────────
    try:
        ride = await service.confirm_ride(ride_token, dock_id)
        await audit.log(
            ride.user_id, "DOCK_SCAN_SUCCESS", "ride", str(ride.id),
            meta=f"dock={dock_id}",
        )
        return success_response(ride.model_dump())
    except AppException as exc:
        await audit.log(
            None, "DOCK_SCAN_CONFIRM_FAIL", "dock", str(dock_id),
            meta=f"code={exc.code}",
        )
        return error_response(exc.code, exc.message, exc.http_status)
