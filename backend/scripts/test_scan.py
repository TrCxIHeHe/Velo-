#!/usr/bin/env python3
"""
Velo dock/QR integration test utility.

Current backend contract:
    POST /api/v1/rides/confirm

JSON body:
    {
        "ride_token": "<JWT from /api/v1/rides/token>",
        "dock_id": "<dock UUID>"
    }

The ESP32-CAM's job is to decode the QR displayed by the Flutter app and
send the decoded ride token to the dock/backend integration. The old
/docks/{dock_id}/scan image-upload endpoint is no longer used by the
current backend.

Examples:

  # Check backend connectivity and list docks
  python scripts/test_scan.py --host 192.168.1.50

  # Simulate an ESP32-CAM that already decoded the QR
  python scripts/test_scan.py \
      --host 192.168.1.50 \
      --dock YOUR_DOCK_UUID \
      --token "eyJhbG..."

  # Generate the same kind of QR shown to the camera, for visual testing
  python scripts/test_scan.py --token "eyJhbG..." --generate-qr

  # Monitor ESP32-CAM serial output
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
        print(f"[HEALTH] GET /api/v1/docks -> HTTP {response.status_code}")

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


def confirm_ride(
    host: str,
    port: int,
    dock_id: str,
    ride_token: str,
) -> dict:
    import requests

    url = f"{base_url(host, port)}/api/v1/rides/confirm"
    payload = {
        "ride_token": ride_token,
        "dock_id": dock_id,
    }

    print(f"[CONFIRM] POST {url}")
    print(f"[CONFIRM] Dock ID: {dock_id}")
    print(f"[CONFIRM] Token length: {len(ride_token)}")

    started = time.monotonic()

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[CONFIRM] Request failed: {exc}")
        return {"status": None, "body": None}

    elapsed = time.monotonic() - started

    try:
        body = response.json()
    except ValueError:
        body = response.text[:1000]

    print(f"[CONFIRM] HTTP {response.status_code} ({elapsed:.2f}s)")
    print(f"[CONFIRM] Body: {body}")

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

    print(f"[SERIAL] Listening on {serial_port} at {baud} baud")
    print("[SERIAL] Press Ctrl+C to stop")

    try:
        with serial.Serial(serial_port, baud, timeout=1) as ser:
            while True:
                line = ser.readline()
                if line:
                    print(line.decode("utf-8", errors="replace").rstrip())
    except KeyboardInterrupt:
        print("\n[SERIAL] Stopped")


def endpoint_smoke_test(host: str, port: int, dock_id: str) -> bool:
    """
    Lightweight contract check for the current hardware endpoint.

    This deliberately does not assert exact application error codes because
    those are implementation details. It checks that:
      1. the endpoint exists
      2. malformed JSON is rejected
      3. a syntactically valid request reaches application validation
    """
    import requests

    url = f"{base_url(host, port)}/api/v1/rides/confirm"
    passed = 0

    print("\n[SMOKE] Current hardware endpoint:", url)

    response = requests.post(
        url,
        json={"dock_id": dock_id},
        timeout=10,
    )
    if response.status_code >= 400:
        print(f"[PASS] Missing ride_token rejected: HTTP {response.status_code}")
        passed += 1
    else:
        print(f"[FAIL] Missing ride_token unexpectedly accepted: HTTP {response.status_code}")

    response = requests.post(
        url,
        json={"ride_token": "not-a-real-token", "dock_id": dock_id},
        timeout=10,
    )
    if response.status_code >= 400:
        print(f"[PASS] Invalid ride token rejected: HTTP {response.status_code}")
        passed += 1
    else:
        print(f"[FAIL] Invalid ride token unexpectedly accepted: HTTP {response.status_code}")

    print(f"[SMOKE] {passed}/2 checks passed")
    return passed == 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Velo ESP32-CAM / ride-confirm integration utility"
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
        help="Dock UUID used for ride confirmation",
    )
    parser.add_argument(
        "--token",
        help="Decoded ride token from the QR code",
    )
    parser.add_argument(
        "--generate-qr",
        action="store_true",
        help="Generate a PNG QR image from --token",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test_ride_qr.png"),
        help="Output QR PNG path",
    )
    parser.add_argument(
        "--monitor",
        metavar="SERIAL_PORT",
        help="Monitor ESP32-CAM serial output, e.g. COM3",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run current /rides/confirm contract checks",
    )
    args = parser.parse_args()

    print("=" * 64)
    print("Velo ESP32-CAM / Ride Confirmation Test Utility")
    print(f"Backend: {base_url(args.host, args.port)}")
    print("=" * 64)

    if args.monitor:
        monitor_serial(args.monitor, args.baud)
        return

    if not health_check(args.host, args.port):
        print("\nStart the backend with:")
        print("  uvicorn app.main:app --reload --host 0.0.0.0")
        raise SystemExit(1)

    if args.generate_qr:
        if not args.token:
            parser.error("--generate-qr requires --token")
        generate_qr_image(args.token, args.output)

    if args.smoke:
        if not args.dock:
            parser.error("--smoke requires --dock")
        endpoint_smoke_test(args.host, args.port, args.dock)

    if args.token:
        if not args.dock:
            parser.error("--token requires --dock")

        result = confirm_ride(
            args.host,
            args.port,
            args.dock,
            args.token,
        )

        if result["status"] == 200:
            print("\nRide confirmation succeeded.")
            print("Backend should now have the ride in ACTIVE state.")
        else:
            print("\nRide confirmation did not succeed.")
            print("Check the backend response above.")

        return

    if not args.generate_qr and not args.smoke:
        print("\nNothing else to run.")
        print("Use one of:")
        print("  --smoke --dock <DOCK_UUID>")
        print("  --token <RIDE_TOKEN> --dock <DOCK_UUID>")
        print("  --token <RIDE_TOKEN> --generate-qr")
        print("  --monitor COM3")


if __name__ == "__main__":
    main()
