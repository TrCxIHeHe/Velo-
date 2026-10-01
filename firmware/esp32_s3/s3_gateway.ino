/**
 * Velo — ESP32-S3 Gateway Firmware (Option A: WiFi + solenoid node)
 * ─────────────────────────────────────────────────────────────────────────────
 * Board  : ESP32-S3 (any dev board with native USB)
 * Role   : Receive JPEG from ESP32-CAM over UART → POST to backend via WiFi
 *          → drive solenoid on success → send ACK byte back to CAM
 *
 * ── Wiring ───────────────────────────────────────────────────────────────────
 *  Programming:
 *    USB cable directly to ESP32-S3 (native USB — no FTDI needed)
 *
 *  UART link from CAM (Serial1):
 *    ESP32-S3 GPIO18 (RX) ← ESP32-CAM GPIO12 (TX)   [921600 baud]
 *    ESP32-S3 GPIO17 (TX) → ESP32-CAM GPIO13 (RX)   [ACK byte]
 *    Shared GND rail
 *
 *  Solenoid (via N-MOSFET, e.g. IRLZ44N):
 *    ESP32-S3 GPIO10 → MOSFET Gate
 *    MOSFET Drain    → Solenoid –
 *    Solenoid +      → 12V supply
 *    12V supply –    → shared GND
 *    Flyback diode across solenoid (cathode → 12V side)
 *
 * ── Frame wire protocol ───────────────────────────────────────────────────────
 *  CAM → S3  : [4 bytes big-endian uint32 length] [length bytes JPEG]
 *  S3  → CAM : [1 byte ACK]  0x4F ('O') = success  |  0x46 ('F') = retry
 *
 * ── Backend HTTP protocol ─────────────────────────────────────────────────────
 *  POST  http://<BACKEND_HOST>:<PORT>/api/v1/docks/<DOCK_ID>/scan
 *  Body  : raw JPEG bytes
 *  Header: Content-Type: image/jpeg
 *  200   → ride confirmed, trigger solenoid
 *  422   → QR not found, send FAIL ACK (CAM retries)
 *  409/410 → token expired/reused, send FAIL ACK (no retry useful)
 *
 * ── Arduino IDE / PlatformIO settings ────────────────────────────────────────
 *   Board         : "ESP32S3 Dev Module" (or your specific board)
 *   USB Mode      : "USB-OTG (TinyUSB)"  or  "Hardware CDC and JTAG"
 *   Upload Mode   : "UART0 / Hardware CDC"
 *   Flash Size    : 4MB (or whatever your board has)
 *   PSRAM         : "OPI PSRAM" if present
 * ─────────────────────────────────────────────────────────────────────────────
 */

#include <WiFi.h>
#include <HTTPClient.h>

// ── User config — change before flashing ──────────────────────────────────────
const char* WIFI_SSID      = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD  = "YOUR_WIFI_PASSWORD";
const char* DOCK_ID        = "YOUR_DOCK_UUID_HERE";   // from GET /api/v1/docks
const char* BACKEND_HOST   = "192.168.1.X";            // Laptop 1 IP running FastAPI
const int   BACKEND_PORT   = 8000;

// ── UART link from CAM ────────────────────────────────────────────────────────
#define CAM_UART_BAUD    921600
#define CAM_UART_RX_PIN   18   // ← ESP32-CAM GPIO12
#define CAM_UART_TX_PIN   17   // → ESP32-CAM GPIO13 (ACK)

// ── Solenoid ──────────────────────────────────────────────────────────────────
#define SOLENOID_PIN        10   // → MOSFET gate
#define SOLENOID_OPEN_MS  3000   // Hold 3 s

// ── Timing & limits ───────────────────────────────────────────────────────────
#define HEADER_TIMEOUT_MS   30000   // Wait up to 30 s for CAM to send a header
#define BODY_TIMEOUT_MS     10000   // Wait up to 10 s for body bytes to arrive
#define HTTP_TIMEOUT_MS     15000   // Backend POST timeout
#define MAX_FRAME_BYTES    200000   // 200 KB — matches backend MAX_IMAGE_BYTES
#define MIN_FRAME_BYTES      1024   // < 1 KB is not a real frame

// ── ACK bytes (must match cam_firmware.ino) ───────────────────────────────────
#define ACK_OK    0x4F   // 'O'
#define ACK_FAIL  0x46   // 'F'

// ── Frame receive buffer — allocated in setup() ───────────────────────────────
uint8_t* frameBuffer = nullptr;

// ── Backend URL (built in setup) ─────────────────────────────────────────────
String backendUrl;

// ══════════════════════════════════════════════════════════════════════════════
// WiFi helpers
// ══════════════════════════════════════════════════════════════════════════════
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connecting");
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) {
    delay(300); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] FAILED — will retry in loop");
  }
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.println("[WiFi] Disconnected — reconnecting...");
  WiFi.reconnect();
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 10000) delay(300);
  return WiFi.status() == WL_CONNECTED;
}

// ══════════════════════════════════════════════════════════════════════════════
// Solenoid
// ══════════════════════════════════════════════════════════════════════════════
void triggerSolenoid() {
  Serial.println("[LOCK] UNLOCKING solenoid...");
  digitalWrite(SOLENOID_PIN, HIGH);
  delay(SOLENOID_OPEN_MS);
  digitalWrite(SOLENOID_PIN, LOW);
  Serial.println("[LOCK] Solenoid closed");
}

// ══════════════════════════════════════════════════════════════════════════════
// Receive a complete frame over Serial1
//
// Blocks until:
//   - 4-byte header arrives (gives length)
//   - All body bytes arrive
// Returns number of bytes read, or 0 on error.
// ══════════════════════════════════════════════════════════════════════════════
size_t receiveFrame() {
  // ── Wait for 4-byte length header ─────────────────────────────────────────
  uint8_t header[4] = {0};
  size_t  headerBytes = 0;
  unsigned long deadline = millis() + HEADER_TIMEOUT_MS;

  while (headerBytes < 4 && millis() < deadline) {
    if (Serial1.available()) {
      header[headerBytes++] = (uint8_t)Serial1.read();
    } else {
      delay(1);
    }
  }

  if (headerBytes < 4) {
    // Timeout waiting for header — no frame arrived this cycle
    return 0;
  }

  uint32_t frameLen = ((uint32_t)header[0] << 24)
                    | ((uint32_t)header[1] << 16)
                    | ((uint32_t)header[2] <<  8)
                    | ((uint32_t)header[3]);

  Serial.printf("[UART] Header received — expecting %u bytes\n", frameLen);

  if (frameLen < MIN_FRAME_BYTES) {
    Serial.printf("[UART] Frame too small (%u bytes) — flushing\n", frameLen);
    // Drain whatever was sent
    unsigned long drain = millis() + 2000;
    while (millis() < drain && Serial1.available()) Serial1.read();
    return 0;
  }

  if (frameLen > MAX_FRAME_BYTES) {
    Serial.printf("[UART] Frame too large (%u bytes) — draining and rejecting\n", frameLen);
    unsigned long drain = millis() + 5000;
    while (millis() < drain && Serial1.available()) Serial1.read();
    return 0;
  }

  // ── Read body bytes ───────────────────────────────────────────────────────
  size_t received = 0;
  deadline = millis() + BODY_TIMEOUT_MS;

  while (received < frameLen && millis() < deadline) {
    int avail = Serial1.available();
    if (avail > 0) {
      size_t toRead = min((size_t)avail, frameLen - received);
      size_t n = Serial1.readBytes(frameBuffer + received, toRead);
      received += n;
    } else {
      delay(1);
    }
  }

  if (received < frameLen) {
    Serial.printf("[UART] Body timeout — got %u / %u bytes\n", received, frameLen);
    return 0;
  }

  Serial.printf("[UART] Frame received: %u bytes\n", received);
  return received;
}

// ══════════════════════════════════════════════════════════════════════════════
// POST JPEG to backend
//
// Returns HTTP status code, or -1 on network error.
// ══════════════════════════════════════════════════════════════════════════════
int postToBackend(size_t frameLen) {
  if (!ensureWiFi()) {
    Serial.println("[HTTP] No WiFi");
    return -1;
  }

  HTTPClient http;
  http.begin(backendUrl);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("Content-Length", String(frameLen));

  int code = http.POST(frameBuffer, frameLen);

  if (code > 0) {
    String body = http.getString();
    Serial.printf("[HTTP] %d — %s\n", code, body.c_str());
  } else {
    Serial.printf("[HTTP] Error: %s\n", http.errorToString(code).c_str());
  }

  http.end();
  return code;
}

// ══════════════════════════════════════════════════════════════════════════════
// Main scan handler — called each loop iteration
// ══════════════════════════════════════════════════════════════════════════════
void handleScan() {
  size_t frameLen = receiveFrame();

  if (frameLen == 0) {
    // No frame or bad frame — nothing to do, CAM will resend
    return;
  }

  int httpCode = postToBackend(frameLen);

  if (httpCode == 200) {
    // Send OK ACK first so CAM can start cooling down while solenoid fires
    Serial1.write(ACK_OK);
    Serial1.flush();
    Serial.println("[SCAN] ✅ Ride confirmed — triggering solenoid");
    triggerSolenoid();
    return;
  }

  if (httpCode == 422) {
    // QR not found in this frame — tell CAM to retry with a fresh capture
    Serial.println("[SCAN] ⚠️  QR not decoded (422) — sending FAIL");
    Serial1.write(ACK_FAIL);
    Serial1.flush();
    return;
  }

  if (httpCode == 409 || httpCode == 410) {
    // Token expired or already used — no point in retrying this QR
    // Send FAIL ACK (CAM will exhaust retries and back off)
    Serial.printf("[SCAN] ❌ Token problem (%d) — sending FAIL\n", httpCode);
    Serial1.write(ACK_FAIL);
    Serial1.flush();
    return;
  }

  // Network error or unexpected status
  Serial.printf("[SCAN] ❌ Unexpected code %d — sending FAIL\n", httpCode);
  Serial1.write(ACK_FAIL);
  Serial1.flush();
}

// ══════════════════════════════════════════════════════════════════════════════
// setup() / loop()
// ══════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);   // Native USB CDC — no baud rate needed on S3, set anyway
  delay(500);
  Serial.println("\n[VELO-S3] Gateway booting...");

  // Solenoid
  pinMode(SOLENOID_PIN, OUTPUT);
  digitalWrite(SOLENOID_PIN, LOW);

  // UART1 to CAM — RX=GPIO18, TX=GPIO17
  // setRxBufferSize must be called before begin()
  Serial1.setRxBufferSize(MAX_FRAME_BYTES + 64);
  Serial1.begin(CAM_UART_BAUD, SERIAL_8N1, CAM_UART_RX_PIN, CAM_UART_TX_PIN);
  Serial.printf("[UART] Serial1 up at %d baud (RX=GPIO%d TX=GPIO%d)\n",
                CAM_UART_BAUD, CAM_UART_RX_PIN, CAM_UART_TX_PIN);

  // Allocate frame buffer in heap (S3 has 512 KB SRAM; 200 KB leaves margin)
  frameBuffer = (uint8_t*)malloc(MAX_FRAME_BYTES);
  if (!frameBuffer) {
    Serial.println("[VELO-S3] FATAL: frame buffer malloc failed — halting");
    while (true) delay(1000);
  }
  Serial.printf("[VELO-S3] Frame buffer: %u KB allocated\n", MAX_FRAME_BYTES / 1024);

  // Build backend URL
  backendUrl = String("http://") + BACKEND_HOST + ":" + BACKEND_PORT
               + "/api/v1/docks/" + DOCK_ID + "/scan";
  Serial.printf("[VELO-S3] Backend URL: %s\n", backendUrl.c_str());

  connectWiFi();

  Serial.println("[VELO-S3] Ready — waiting for frames from CAM");
}

void loop() {
  handleScan();
  // No delay here — receiveFrame() itself blocks on Serial1 up to HEADER_TIMEOUT_MS.
  // If no frame arrives within that window it returns 0 and we loop immediately.
}
