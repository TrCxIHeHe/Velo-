"""
dock_vision/router.py — HTTP layer for ESP32-CAM QR scan endpoint.
"""

import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock_vision.service import QrDecodeError, decode_qr_with_strategy
from app.ride.router import RideServiceDep

router = APIRouter(prefix="/docks", tags=["dock-vision"])
logger = logging.getLogger(__name__)

# ── Development-only scan debugging ──────────────────────────────────────────
# backend/debug_scans/latest.jpg
#     The frame of the CURRENT scan cycle.  Written synchronously the moment a
#     frame arrives — before any validation or QR decoding — so it can never
#     lag behind the frame being processed.  Overwritten by every new frame.
# backend/debug_scans/success_<YYYYMMDD_HHMMSS_mmm>.jpg
# backend/debug_scans/failure_<YYYYMMDD_HHMMSS_mmm>.jpg
#     One permanent file per received frame, named after the FINAL outcome
#     (success = ride confirmed; failure = anything else: no QR found, QR
#     decoded but token rejected, oversize/undersize frame, server error).
#     Never overwritten (created with O_EXCL; a numeric suffix is added on the
#     rare same-millisecond collision).  Times are server-local.
DEBUG_SAVE_SCANS = True
DEBUG_SCAN_DIR = Path(__file__).resolve().parents[2] / "debug_scans"


def save_latest_image(image_bytes: bytes) -> None:
    """Write debug_scans/latest.jpg immediately (synchronous by design)."""
    if not DEBUG_SAVE_SCANS:
        return
    try:
        DEBUG_SCAN_DIR.mkdir(parents=True, exist_ok=True)
        target = DEBUG_SCAN_DIR / "latest.jpg"
        tmp = DEBUG_SCAN_DIR / "latest.jpg.tmp"
        tmp.write_bytes(image_bytes)
        try:
            # Atomic swap: a viewer never sees a half-written latest.jpg.
            os.replace(tmp, target)
        except PermissionError:
            # Windows: target is open in an image viewer — write in place.
            target.write_bytes(image_bytes)
            tmp.unlink(missing_ok=True)
        logger.info("[SCAN] Saved latest.jpg")
    except OSError as exc:
        logger.warning("[SCAN] Could not save latest.jpg: %s", exc)


def save_history_image(outcome: str, image_bytes: bytes) -> None:
    """Persist a unique, never-overwritten historical image for this frame."""
    if not DEBUG_SAVE_SCANS:
        return
    try:
        DEBUG_SCAN_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        stamp = f"{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}"
        for attempt in range(1000):
            suffix = "" if attempt == 0 else f"_{attempt}"
            name = f"{outcome}_{stamp}{suffix}.jpg"
            try:
                # "xb" = exclusive create: fails instead of overwriting.
                with open(DEBUG_SCAN_DIR / name, "xb") as fh:
                    fh.write(image_bytes)
            except FileExistsError:
                continue
            logger.info("[SCAN] Saved %s", name)
            return
        logger.warning("[SCAN] Could not find a free filename for %s_%s", outcome, stamp)
    except OSError as exc:
        logger.warning("[SCAN] Could not save %s image: %s", outcome, exc)


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

    logger.info("[SCAN] Frame received: %d bytes (dock=%s)", len(image_bytes), dock_id)

    # 1) The current frame is on disk BEFORE anything can reject or fail on it.
    save_latest_image(image_bytes)

    # 2) Exactly one historical file per frame, named after the final outcome.
    #    The default is "failure"; only a confirmed ride flips it to "success".
    #    try/finally guarantees the frame is archived even if decoding or the
    #    database raises.
    outcome = "failure"
    try:
        if len(image_bytes) > MAX_IMAGE_BYTES:
            logger.info("[SCAN] Rejected: image too large (%d bytes)", len(image_bytes))
            return error_response(
                "DOCK_SCAN_IMAGE_TOO_LARGE",
                f"Image exceeds {MAX_IMAGE_BYTES // 1024} KB limit.",
                413,
            )

        if len(image_bytes) < MIN_IMAGE_BYTES:
            logger.info("[SCAN] Rejected: image too small (%d bytes)", len(image_bytes))
            return error_response(
                "DOCK_SCAN_IMAGE_TOO_SMALL",
                "Image too small to be a real camera frame.",
                422,
            )

        audit = AuditLogRepository(session)

        try:
            decode_start = time.perf_counter()
            ride_token, strategy = decode_qr_with_strategy(image_bytes)
            decode_ms = (time.perf_counter() - decode_start) * 1000
            logger.info("[SCAN] QR decoded via %s in %.1f ms", strategy, decode_ms)
        except QrDecodeError as exc:
            total_ms = (time.perf_counter() - scan_start) * 1000
            logger.info("[SCAN] QR not found (%.1f ms): %s", total_ms, exc)

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

        # The QR decoded.  Whether the token is acceptable is a separate
        # question (invalid / expired / wrong dock / reused / no vehicle).
        try:
            ride = await service.confirm_ride(ride_token, dock_id)
        except AppException as exc:
            total_ms = (time.perf_counter() - scan_start) * 1000
            logger.info(
                "[SCAN] QR decoded but scan rejected: %s (%.1f ms)", exc.code, total_ms
            )

            await audit.log(
                None,
                "DOCK_SCAN_CONFIRM_FAIL",
                "dock",
                str(dock_id),
                meta=f"code={exc.code}",
            )

            return error_response(exc.code, exc.message, exc.http_status)

        outcome = "success"
        total_ms = (time.perf_counter() - scan_start) * 1000
        logger.info("[SCAN] SUCCESS — ride %s confirmed (%.1f ms)", ride.id, total_ms)

        await audit.log(
            ride.user_id,
            "DOCK_SCAN_SUCCESS",
            "ride",
            str(ride.id),
            meta=f"dock={dock_id}",
        )

        return success_response(ride.model_dump())
    finally:
        save_history_image(outcome, image_bytes)
