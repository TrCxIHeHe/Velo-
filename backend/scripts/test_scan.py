#!/usr/bin/env python3
"""
Velo dock-vision / ESP32 integration test utility.

Current Option A hardware contract:

    ESP32-CAM
        │
        │ 4-byte big-endian JPEG length + JPEG bytes
        │ UART 921600
        ▼
    ESP32-S3
        │
        │ POST /api/v1/docks/{dock_id}/scan
        │ Content-Type: image/jpeg
        ▼
    FastAPI
        │
        ├── QR decode
        └── RideService.confirm_ride()
        │
        ▼
    HTTP response
        │
        └── ESP32-S3 sends ACK to CAM

The backend endpoint accepts a raw JPEG body, NOT multipart/form-data
and NOT JSON.

Examples:

  # Check backend connectivity
  python scripts/test_scan.py --host 192.168.1.50

  # Test the current /docks/{dock_id}/scan endpoint with a JPEG
  python scripts/test_scan.py \
      --host 192.168.1.50 \
      --dock YOUR_DOCK_UUID \
      --image test_ride_qr.png

  # Generate a QR image from a ride token for camera testing
  python scripts/test_scan.py \
      --token "eyJhbG..." \
      --generate-qr

  # Generate QR and immediately upload it to the dock scan endpoint
  python scripts/test_scan.py \
      --host 192.168.1.50 \
      --dock YOUR_DOCK_UUID \
      --token "eyJhbG..." \
      --generate-qr \
      --scan

  # Monitor ESP32-S3 serial output
  python scripts/test_scan.py --monitor COM3

Requirements:
    pip install requests
    pip install qrcode pillow       # only for --generate-qr
    pip install pyserial             # only for --monitor
"""

import argparse
import sys
import time
from pathlib import Path


def base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def health_check(host: str, port: int) -> bool:
    import requests

    url = f"{base_url(host, port)}/api/v1/docks"

    try:
        response = requests.get(url, timeout=5)

        print(
            f"[HEALTH] GET /api/v1/docks "
            f"-> HTTP {response.status_code}"
        )

        if response.ok:
            try:
                body = response.json()
                print(f"[HEALTH] Response: {body}")
            except ValueError:
                pass

            return True

        return False

    except requests.RequestException as exc:
        print(f"[HEALTH] Cannot reach backend: {exc}")
        return False


def scan_image(
    host: str,
    port: int,
    dock_id: str,
    image_path: Path,
) -> dict:
    """
    Send a raw JPEG image to the same endpoint used by the ESP32-S3.

    This intentionally mirrors the S3 firmware:

        POST /api/v1/docks/{dock_id}/scan
        Content-Type: image/jpeg
        Body: raw JPEG bytes
    """
    import requests

    if not image_path.exists():
        print(f"[SCAN] Image not found: {image_path}")
        return {"status": None, "body": None}

    image_bytes = image_path.read_bytes()

    if not image_bytes:
        print("[SCAN] Image is empty")
        return {"status": None, "body": None}

    url = (
        f"{base_url(host, port)}"
        f"/api/v1/docks/{dock_id}/scan"
    )

    print(f"[SCAN] POST {url}")
    print(f"[SCAN] Dock ID: {dock_id}")
    print(f"[SCAN] Image: {image_path}")
    print(f"[SCAN] Image size: {len(image_bytes)} bytes")

    started = time.monotonic()

    try:
        response = requests.post(
            url,
            headers={
                "Content-Type": "image/jpeg",
                "Content-Length": str(len(image_bytes)),
            },
            data=image_bytes,
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"[SCAN] Request failed: {exc}")
        return {"status": None, "body": None}

    elapsed = time.monotonic() - started

    try:
        body = response.json()
    except ValueError:
        body = response.text[:1000]

    print(
        f"[SCAN] HTTP {response.status_code} "
        f"({elapsed:.2f}s)"
    )
    print(f"[SCAN] Body: {body}")

    if response.status_code == 200:
        print("[SCAN] SUCCESS — QR decoded and ride confirmed.")
    elif response.status_code == 422:
        print("[SCAN] QR was not found in the image.")
    elif response.status_code == 409:
        print("[SCAN] Ride/token/dock state rejected the scan.")
    elif response.status_code == 410:
        print("[SCAN] Ride token has expired.")
    elif response.status_code == 413:
        print("[SCAN] Image exceeded the backend size limit.")
    elif response.status_code == 415:
        print("[SCAN] Invalid Content-Type.")
    else:
        print("[SCAN] Scan failed.")

    return {
        "status": response.status_code,
        "body": body,
    }


def generate_qr_image(token: str, output: Path) -> Path:
    try:
        import qrcode
    except ImportError:
        print("ERROR: install QR dependencies with:")
        print("  pip install qrcode pillow")
        raise SystemExit(1)

    image = qrcode.make(token)
    image.save(output)

    print(f"[QR] Generated: {output.resolve()}")
    return output


def monitor_serial(serial_port: str, baud: int) -> None:
    try:
        import serial
    except ImportError:
        print("ERROR: install pyserial with:")
        print("  pip install pyserial")
        raise SystemExit(1)

    print(
        f"[SERIAL] Listening on {serial_port} "
        f"at {baud} baud"
    )
    print("[SERIAL] Press Ctrl+C to stop")

    try:
        with serial.Serial(
            serial_port,
            baud,
            timeout=1,
        ) as ser:
            while True:
                line = ser.readline()

                if line:
                    print(
                        line.decode(
                            "utf-8",
                            errors="replace",
                        ).rstrip()
                    )

    except KeyboardInterrupt:
        print("\n[SERIAL] Stopped")


def endpoint_smoke_test(
    host: str,
    port: int,
    dock_id: str,
) -> bool:
    """
    Lightweight contract check for the current hardware endpoint.

    Checks that:

      1. POST /docks/{dock_id}/scan exists.
      2. Non-image content types are rejected.
      3. Tiny image payloads are rejected.
      4. A valid JPEG reaches QR decoding.

    No real ride is created unless a valid ride-token QR is supplied.
    """
    import requests

    url = (
        f"{base_url(host, port)}"
        f"/api/v1/docks/{dock_id}/scan"
    )

    passed = 0
    total = 3

    print("\n[SMOKE] Current hardware endpoint:")
    print(f"        {url}")

    # ── Check 1: Content-Type validation ───────────────────────────────

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        data=b'{"dummy": true}',
        timeout=10,
    )

    if response.status_code == 415:
        print(
            "[PASS] Non-image Content-Type rejected: "
            f"HTTP {response.status_code}"
        )
        passed += 1
    else:
        print(
            "[FAIL] Expected HTTP 415 for non-image body; "
            f"got HTTP {response.status_code}"
        )

    # ── Check 2: Minimum image-size validation ─────────────────────────

    response = requests.post(
        url,
        headers={"Content-Type": "image/jpeg"},
        data=b"\xff\xd8" * 100,
        timeout=10,
    )

    if response.status_code == 422:
        print(
            "[PASS] Tiny image rejected: "
            f"HTTP {response.status_code}"
        )
        passed += 1
    else:
        print(
            "[FAIL] Expected HTTP 422 for tiny image; "
            f"got HTTP {response.status_code}"
        )

    # ── Check 3: Valid JPEG reaches QR decoder ──────────────────────────

    try:
        import cv2
        import numpy as np

        image = np.zeros(
            (240, 320, 3),
            dtype=np.uint8,
        )

        # Add enough structure for a real JPEG payload while
        # deliberately containing no QR code.
        for y in range(0, 240, 10):
            image[y:y + 5, :] = 255

        success, encoded = cv2.imencode(
            ".jpg",
            image,
            [
                int(cv2.IMWRITE_JPEG_QUALITY),
                80,
            ],
        )

        if not success:
            raise RuntimeError("Could not encode test JPEG")

        jpeg_bytes = encoded.tobytes()

    except ImportError:
        print(
            "[SKIP] OpenCV is required for the valid-JPEG smoke test."
        )
        total -= 1
    except Exception as exc:
        print(f"[SKIP] Could not create test JPEG: {exc}")
        total -= 1
    else:
        response = requests.post(
            url,
            headers={"Content-Type": "image/jpeg"},
            data=jpeg_bytes,
            timeout=15,
        )

        if response.status_code == 422:
            print(
                "[PASS] Valid JPEG reached QR decoder: "
                f"HTTP {response.status_code}"
            )
            passed += 1
        else:
            print(
                "[FAIL] Expected HTTP 422 for JPEG without QR; "
                f"got HTTP {response.status_code}"
            )

    print(f"[SMOKE] {passed}/{total} checks passed")

    return passed == total


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Velo ESP32-CAM / ESP32-S3 dock-vision "
            "integration utility"
        )
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Backend host/IP (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)",
    )

    parser.add_argument(
        "--dock",
        help="Dock UUID used by the scan endpoint",
    )

    parser.add_argument(
        "--image",
        type=Path,
        help=(
            "JPEG image to upload directly to the "
            "dock-vision endpoint"
        ),
    )

    parser.add_argument(
        "--token",
        help="Ride token to encode into a QR image",
    )

    parser.add_argument(
        "--generate-qr",
        action="store_true",
        help="Generate a PNG QR image from --token",
    )

    parser.add_argument(
        "--scan",
        action="store_true",
        help=(
            "Upload --image (or the generated QR image) "
            "to /docks/{dock_id}/scan"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test_ride_qr.png"),
        help=(
            "Output QR PNG path "
            "(default: test_ride_qr.png)"
        ),
    )

    parser.add_argument(
        "--monitor",
        metavar="SERIAL_PORT",
        help=(
            "Monitor ESP32 serial output, "
            "e.g. COM3"
        ),
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200)",
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Run checks against the current "
            "dock-vision endpoint"
        ),
    )

    args = parser.parse_args()

    print("=" * 64)
    print("Velo ESP32-CAM / ESP32-S3 Dock Vision Test Utility")
    print(f"Backend: {base_url(args.host, args.port)}")
    print("=" * 64)

    # Serial monitor does not require a backend.
    if args.monitor:
        monitor_serial(args.monitor, args.baud)
        return

    if not health_check(args.host, args.port):
        print("\nStart the backend with:")
        print(
            "  uvicorn app.main:app "
            "--reload --host 0.0.0.0"
        )
        raise SystemExit(1)

    # ── Generate QR ────────────────────────────────────────────────────

    generated_image = None

    if args.generate_qr:
        if not args.token:
            parser.error(
                "--generate-qr requires --token"
            )

        generated_image = generate_qr_image(
            args.token,
            args.output,
        )

    # ── Smoke test ────────────────────────────────────────────────────

    if args.smoke:
        if not args.dock:
            parser.error("--smoke requires --dock")

        success = endpoint_smoke_test(
            args.host,
            args.port,
            args.dock,
        )

        if not success:
            raise SystemExit(1)

    # ── Direct image scan ─────────────────────────────────────────────

    if args.scan:
        if not args.dock:
            parser.error("--scan requires --dock")

        image_path = args.image or generated_image

        if image_path is None:
            parser.error(
                "--scan requires --image or "
                "--generate-qr"
            )

        result = scan_image(
            args.host,
            args.port,
            args.dock,
            image_path,
        )

        if result["status"] != 200:
            raise SystemExit(1)

    # ── Convenience: --image without --scan ───────────────────────────

    if args.image and not args.scan:
        print(
            "\nImage supplied but not uploaded."
        )
        print(
            "Use --scan to send it to the "
            "dock-vision endpoint."
        )

    # ── Nothing else ──────────────────────────────────────────────────

    if (
        not args.generate_qr
        and not args.smoke
        and not args.scan
        and not args.image
    ):
        print("\nNothing else to run.")
        print("\nExamples:")
        print(
            "  --smoke --dock <DOCK_UUID>"
        )
        print(
            "  --image frame.jpg "
            "--dock <DOCK_UUID> --scan"
        )
        print(
            "  --token <RIDE_TOKEN> "
            "--generate-qr"
        )
        print(
            "  --token <RIDE_TOKEN> "
            "--generate-qr "
            "--dock <DOCK_UUID> --scan"
        )
        print(
            "  --monitor COM3"
        )


if __name__ == "__main__":
    main()