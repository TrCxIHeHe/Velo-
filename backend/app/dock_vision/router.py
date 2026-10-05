"""
dock_vision/router.py — HTTP layer for ESP32-CAM QR scan endpoint.
"""

import logging
import time
import uuid
from pathlib import Path
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
logger = logging.getLogger(__name__)

# Development-only scan debugging.
# These files let us inspect exactly what the ESP32-CAM produced.
#
# backend/debug_scans/latest.jpg
# backend/debug_scans/last_fail.jpg
# backend/debug_scans/last_success.jpg
DEBUG_SAVE_SCANS = True
DEBUG_SCAN_DIR = Path(__file__).resolve().parents[2] / "debug_scans"


def save_debug_image(filename: str, image_bytes: bytes) -> None:
    if not DEBUG_SAVE_SCANS:
        return

    try:
        DEBUG_SCAN_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_SCAN_DIR / filename
        path.write_bytes(image_bytes)
        logger.info("Debug scan image saved: %s", path)
    except OSError as exc:
        logger.warning(
            "Could not save debug scan %s: %s",
            filename,
            exc,
        )


# OV2640 frames are expected to be small; keep a generous hard limit.
MAX_IMAGE_BYTES = 200 * 1024
MIN_IMAGE_BYTES = 1_024


@router.post("/{dock_id}/scan")
@limiter.limit("20/minute")
async def scan_dock_image(
    dock_id: uuid.UUID,
    request: Request,
    service: RideServiceDep,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Accept a raw JPEG body from the ESP32-S3.
    No multipart/form-data is required.
    """

    scan_start = time.perf_counter()

    content_type = request.headers.get("content-type", "")

    if "image" not in content_type.lower():
        logger.info(
            "Dock scan rejected: invalid content type %r",
            content_type,
        )
        return error_response(
            "DOCK_SCAN_INVALID_CONTENT_TYPE",
            "Expected Content-Type: image/jpeg.",
            415,
        )

    image_bytes = await request.body()

    logger.info(
        "Dock scan received: dock=%s bytes=%d",
        dock_id,
        len(image_bytes),
    )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        logger.info(
            "Dock scan rejected: image too large (%d bytes)",
            len(image_bytes),
        )
        return error_response(
            "DOCK_SCAN_IMAGE_TOO_LARGE",
            f"Image exceeds {MAX_IMAGE_BYTES // 1024} KB limit.",
            413,
        )

    if len(image_bytes) < MIN_IMAGE_BYTES:
        save_debug_image("latest.jpg", image_bytes)
        save_debug_image("last_fail.jpg", image_bytes)

        logger.info(
            "Dock scan rejected: image too small (%d bytes)",
            len(image_bytes),
        )

        return error_response(
            "DOCK_SCAN_IMAGE_TOO_SMALL",
            "Image too small to be a real camera frame.",
            422,
        )

    # Always keep the most recent frame for physical debugging.
    save_debug_image("latest.jpg", image_bytes)

    audit = AuditLogRepository(session)

    try:
        decode_start = time.perf_counter()
        ride_token = decode_qr_from_image_bytes(image_bytes)
        decode_ms = (time.perf_counter() - decode_start) * 1000

        logger.info(
            "Dock scan QR decoded in %.1f ms",
            decode_ms,
        )

    except QrDecodeError as exc:
        save_debug_image("last_fail.jpg", image_bytes)

        total_ms = (time.perf_counter() - scan_start) * 1000

        logger.info(
            "Dock scan QR not found in %.1f ms: %s",
            total_ms,
            exc,
        )

        await audit.log(
            None,
            "DOCK_SCAN_FAIL",
            "dock",
            str(dock_id),
            meta=f"bytes={len(image_bytes)} reason={exc}",
        )

        return error_response(
            "DOCK_SCAN_QR_NOT_FOUND",
            str(exc),
            422,
        )

    try:
        ride = await service.confirm_ride(
            ride_token,
            dock_id,
        )

        save_debug_image(
            "last_success.jpg",
            image_bytes,
        )

        total_ms = (time.perf_counter() - scan_start) * 1000

        logger.info(
            "Dock scan SUCCESS in %.1f ms",
            total_ms,
        )

        await audit.log(
            ride.user_id,
            "DOCK_SCAN_SUCCESS",
            "ride",
            str(ride.id),
            meta=f"dock={dock_id}",
        )

        return success_response(
            ride.model_dump()
        )

    except AppException as exc:
        save_debug_image(
            "last_fail.jpg",
            image_bytes,
        )

        total_ms = (time.perf_counter() - scan_start) * 1000

        logger.info(
            "Dock scan confirmation failed in %.1f ms: %s",
            total_ms,
            exc.code,
        )

        await audit.log(
            None,
            "DOCK_SCAN_CONFIRM_FAIL",
            "dock",
            str(dock_id),
            meta=f"code={exc.code}",
        )

        return error_response(
            exc.code,
            exc.message,
            exc.http_status,
        )
