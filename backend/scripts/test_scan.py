#!/usr/bin/env python3
"""
test_scan.py — Velo Dock Vision Test Utility
═══════════════════════════════════════════════════════════════════════════════
Run this on the Arduino laptop (or any machine on the same network) to test the
entire QR scan → backend → ride confirm pipeline without needing the physical
ESP32-CAM hardware connected.

Usage:
  python test_scan.py --host 192.168.1.X --dock YOUR_DOCK_UUID [options]

Examples:
  # Test with a QR code image file
  python test_scan.py --host 192.168.1.50 --dock 3fa85f64-5717-4562-b3fc-2c963f66afa6 --image qr.jpg

  # Screenshot the Flutter QR screen → save as qr.png → test it
  python test_scan.py --host 192.168.1.50 --dock 3fa85f64-... --image qr.png

  # Generate a test QR image locally and scan it (needs: pip install qrcode pillow)
  python test_scan.py --host 192.168.1.50 --dock 3fa85f64-... --token "eyJhbG..."

  # Watch mode: monitor the serial port of a connected ESP32-CAM
  python test_scan.py --host 192.168.1.50 --dock 3fa85f64-... --monitor COM3

Requirements:
  pip install requests qrcode pillow pyserial
═══════════════════════════════════════════════════════════════════════════════
"""
import argparse
import io
import sys
import time
from pathlib import Path


# ─── HTTP scan call ───────────────────────────────────────────────────────────

def scan_image_file(host: str, port: int, dock_id: str, image_path: Path) -> dict:
    """POST a JPEG/PNG file to the backend scan endpoint and return the response."""
    import requests

    url = f"http://{host}:{port}/api/v1/docks/{dock_id}/scan"
    image_bytes = image_path.read_bytes()

    # Detect content type from extension
    ext = image_path.suffix.lower()
    content_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    print(f"  → POST {url}")
    print(f"  → Image: {image_path.name} ({len(image_bytes):,} bytes, {content_type})")

    start = time.monotonic()
    resp = requests.post(
        url,
        data=image_bytes,
        headers={"Content-Type": content_type},
        timeout=20,
    )
    elapsed = time.monotonic() - start

    print(f"  ← HTTP {resp.status_code}  ({elapsed:.2f} s)")
    try:
        body = resp.json()
        print(f"  ← Body: {body}")
    except Exception:
        print(f"  ← Body (raw): {resp.text[:500]}")

    return {"status": resp.status_code, "body": resp.json() if resp.ok else None}


# ─── Generate QR image from a token string ───────────────────────────────────

def generate_qr_image(token: str) -> Path:
    """Create a test QR code PNG from a raw token string. Returns the file path."""
    try:
        import qrcode
    except ImportError:
        print("ERROR: pip install qrcode pillow")
        sys.exit(1)

    img = qrcode.make(token)
    path = Path("test_qr_generated.png")
    img.save(str(path))
    print(f"[QR] Generated test QR → {path}")
    return path


# ─── Backend health check ─────────────────────────────────────────────────────

def health_check(host: str, port: int) -> bool:
    import requests
    url = f"http://{host}:{port}/api/v1/docks"
    try:
        r = requests.get(url, timeout=5)
        print(f"[HEALTH] GET /docks → HTTP {r.status_code} ✅")
        return True
    except Exception as e:
        print(f"[HEALTH] Cannot reach backend at {host}:{port} — {e}")
        return False


# ─── Serial monitor ───────────────────────────────────────────────────────────

def monitor_serial(port: str, baud: int = 115200):
    """Stream ESP32-CAM Serial output to the console for live debugging."""
    try:
        import serial
    except ImportError:
        print("ERROR: pip install pyserial")
        sys.exit(1)

    print(f"\n[MONITOR] Listening on {port} at {baud} baud. Press Ctrl+C to stop.\n")
    with serial.Serial(port, baud, timeout=1) as ser:
        while True:
            line = ser.readline()
            if line:
                print(line.decode("utf-8", errors="replace").rstrip())


# ─── Quick connectivity test: check scan endpoint accepts/rejects correctly ───

def run_endpoint_tests(host: str, port: int, dock_id: str):
    """
    Smoke-test the scan endpoint behaviour without a real QR image.
    Validates: Content-Type rejection, size rejection, empty body.
    """
    import requests

    base = f"http://{host}:{port}/api/v1/docks/{dock_id}/scan"
    print("\n[TESTS] Running endpoint smoke tests...")

    tests = [
        {
            "name": "Reject non-image Content-Type",
            "headers": {"Content-Type": "application/json"},
            "body": b'{"test": 1}',
            "expect": 415,
        },
        {
            "name": "Reject empty body",
            "headers": {"Content-Type": "image/jpeg"},
            "body": b"",
            "expect": 422,
        },
        {
            "name": "Reject tiny body (< 1 KB)",
            "headers": {"Content-Type": "image/jpeg"},
            "body": b"\xff\xd8" * 100,   # fake JPEG marker, 200 bytes
            "expect": 422,
        },
        {
            "name": "Reject oversized body (> 200 KB)",
            "headers": {"Content-Type": "image/jpeg"},
            "body": b"\x00" * (210 * 1024),
            "expect": 413,
        },
    ]

    passed = 0
    for t in tests:
        r = requests.post(base, data=t["body"], headers=t["headers"], timeout=10)
        status = "✅ PASS" if r.status_code == t["expect"] else f"❌ FAIL (got {r.status_code})"
        print(f"  {status}  {t['name']}")
        if r.status_code == t["expect"]:
            passed += 1

    print(f"\n[TESTS] {passed}/{len(tests)} passed\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Velo Dock Vision test utility")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Backend host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000,
                        help="Backend port (default: 8000)")
    parser.add_argument("--dock", required=True,
                        help="Dock UUID (from GET /api/v1/docks)")
    parser.add_argument("--image", type=Path, default=None,
                        help="Path to a JPEG/PNG file to scan")
    parser.add_argument("--token", default=None,
                        help="Raw ride token string — generates a QR image and scans it")
    parser.add_argument("--monitor", default=None, metavar="PORT",
                        help="Serial port to monitor (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--smoke", action="store_true",
                        help="Run endpoint smoke tests (no real QR needed)")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Serial baud rate (default: 115200)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Velo DockVision Test Utility")
    print(f"  Backend : http://{args.host}:{args.port}")
    print(f"  Dock ID : {args.dock}")
    print("=" * 60)

    # Serial monitor mode — blocks until Ctrl+C
    if args.monitor:
        monitor_serial(args.monitor, args.baud)
        return

    # Health check first
    if not health_check(args.host, args.port):
        print("\nMake sure the backend is running on the main laptop:")
        print("  cd backend && uvicorn app.main:app --reload --host 0.0.0.0")
        sys.exit(1)

    # Smoke tests
    if args.smoke:
        run_endpoint_tests(args.host, args.port, args.dock)

    # Scan with a token → generate QR first
    if args.token:
        image_path = generate_qr_image(args.token)
        result = scan_image_file(args.host, args.port, args.dock, image_path)
        if result["status"] == 200:
            print("\n✅ Ride activated! Full pipeline working end-to-end.")
        elif result["status"] == 422:
            print("\n⚠️  QR not decoded — check image quality or backend service.py preprocessing.")
        else:
            print(f"\n❌ Unexpected status: {result['status']}")
        return

    # Scan with an existing image file
    if args.image:
        if not args.image.exists():
            print(f"ERROR: Image file not found: {args.image}")
            sys.exit(1)
        result = scan_image_file(args.host, args.port, args.dock, args.image)
        if result["status"] == 200:
            print("\n✅ Ride activated! Full pipeline working end-to-end.")
        elif result["status"] == 422:
            print("\n⚠️  QR not decoded — try a clearer image.")
        else:
            print(f"\n❌ Unexpected status: {result['status']}")
        return

    if not args.smoke:
        print("\nNothing to do. Use --image, --token, --monitor, or --smoke.")
        parser.print_help()


if __name__ == "__main__":
    main()
