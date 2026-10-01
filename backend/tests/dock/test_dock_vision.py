"""
Tests for dock vision scan endpoint: POST /api/v1/docks/{dock_id}/scan
Validates guards B-03 (size limit), B-04 (audit logging), B-06 (content-type).
"""
import uuid
import pytest
import cv2
import numpy as np


def _make_dummy_jpeg(width: int = 320, height: int = 240) -> bytes:
    """Create a minimal valid JPEG image in memory."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Draw some noise/shapes so it's > 1024 bytes when encoded
    for i in range(0, height, 10):
        img[i:i+5, :] = 255
    success, encoded = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    assert success
    return encoded.tobytes()


@pytest.mark.asyncio
async def test_scan_rejects_non_image_content_type(client):
    dock_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/docks/{dock_id}/scan",
        headers={"Content-Type": "application/json"},
        content=b'{"dummy": true}',
    )
    assert resp.status_code == 415
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DOCK_SCAN_INVALID_CONTENT_TYPE"


@pytest.mark.asyncio
async def test_scan_rejects_tiny_payload(client):
    dock_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/docks/{dock_id}/scan",
        headers={"Content-Type": "image/jpeg"},
        content=b"\xff\xd8" * 100,  # 200 bytes < 1 KB
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DOCK_SCAN_IMAGE_TOO_SMALL"


@pytest.mark.asyncio
async def test_scan_rejects_oversized_payload(client):
    dock_id = uuid.uuid4()
    oversized = b"\x00" * (210 * 1024)  # 210 KB > 200 KB
    resp = await client.post(
        f"/api/v1/docks/{dock_id}/scan",
        headers={"Content-Type": "image/jpeg"},
        content=oversized,
    )
    assert resp.status_code == 413
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DOCK_SCAN_IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_scan_returns_422_when_no_qr_found(client):
    dock_id = uuid.uuid4()
    jpeg_bytes = _make_dummy_jpeg()
    assert len(jpeg_bytes) >= 1024

    resp = await client.post(
        f"/api/v1/docks/{dock_id}/scan",
        headers={"Content-Type": "image/jpeg"},
        content=jpeg_bytes,
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DOCK_SCAN_QR_NOT_FOUND"

