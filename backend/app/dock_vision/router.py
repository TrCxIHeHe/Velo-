import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.audit.repository import AuditLogRepository
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.dock_vision.service import QrDecodeError, decode_qr_from_image_bytes
from app.ride.router import RideServiceDep  # reuse existing DI wiring — no duplicate service construction

router = APIRouter(prefix="/docks", tags=["dock-vision"])

# 5 MB — a 320x240 q50 JPEG is ~10-15KB; this is a generous ceiling against
# a misconfigured camera sending full-res frames, not a tuned limit.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/{dock_id}/scan")
async def scan_dock_image(
    dock_id: uuid.UUID,
    file: UploadFile,
    service: RideServiceDep,
):
    """Called directly by dock-side ESP32-CAM firmware. No user auth —
    same posture as /rides/confirm: the decoded ride_token IS the
    credential once extracted. Unauthenticated at the transport level
    for MVP (LAN-only); add X-Dock-Key header validation before this
    is ever reachable over the public internet.
    """
    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return error_response("DOCK_SCAN_IMAGE_TOO_LARGE", "Image exceeds size limit.", 413)

    try:
        ride_token = decode_qr_from_image_bytes(image_bytes)
    except QrDecodeError as exc:
        return error_response("DOCK_SCAN_QR_NOT_FOUND", str(exc), 422)

    try:
        ride = await service.confirm_ride(ride_token, dock_id)
        return success_response(ride.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)