# app/dock_vision/router.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.audit.repository import AuditLogRepository
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.dock_vision.service import QrDecodeError, decode_qr_from_image_bytes
from app.ride.router import RideServiceDep

router = APIRouter(prefix="/docks", tags=["dock-vision"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/{dock_id}/scan")
async def scan_dock_image(
    dock_id: uuid.UUID,
    request: Request,
    service: RideServiceDep,
):
    """Accepts a raw JPEG body (Content-Type: image/jpeg), as sent by the
    ESP32-CAM firmware directly — not multipart/form-data. Kept as raw
    bytes on purpose: multipart encoding requires the device to malloc a
    boundary-wrapped buffer, which raw POST avoids entirely."""
    image_bytes = await request.body()
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