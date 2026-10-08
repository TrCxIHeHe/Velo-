/**
 * Velo — ESP32-S3 Gateway Firmware (Option A: WiFi node)
 * Board  : ESP32-S3 N8R2
 * Role   : Receive JPEG from ESP32-CAM over UART → POST to backend via WiFi
 *          → send final scan ACK byte back to CAM.
 *
 * Current demo hardware:
 *   Solenoid path is explicitly DISABLED.
 *
 * UART:
 *   ESP32-S3 GPIO18 (RX) ← ESP32-CAM GPIO12 (TX)
 *   ESP32-S3 GPIO17 (TX) → ESP32-CAM GPIO13 (RX)
 *   Shared GND
 *
 * Frame wire protocol:
 *   CAM → S3  : [4 bytes big-endian uint32 length] [length bytes JPEG]
 *   S3  → CAM : [1 byte ACK]
 *              0x4F ('O') = success
 *              0x46 ('F') = retry
 *
 * ACK protocol limitation (deliberately NOT changed):
 *   The 1-byte ACK can only say "accepted" (0x4F) or "not accepted" (0x46).
 *   The S3 classifies every backend outcome (see ScanOutcome below) and logs
 *   it, but all non-success outcomes map to 0x46, so the CAM cannot tell
 *   "QR not found" (retry is useful) from "token expired/reused/wrong dock"
 *   (retrying the same QR cannot succeed) or from a backend/network failure.
 *   The CAM's bounded retry count (MAX_SCAN_RETRIES) is what limits wasted
 *   retries.  Telling these apart on the CAM would need a protocol change.
 *
 * Arduino IDE:
 *   Board     : ESP32S3 Dev Module
 *   Flash     : 8MB
 *   PSRAM     : QSPI PSRAM
 */

#include <WiFi.h>
#include <HTTPClient.h>

// WiFi/backend config
const char* WIFI_SSID      = "Vishisht's S24";
const char* WIFI_PASSWORD  = "124vishi";
const char* DOCK_ID        = "33333333-3333-3333-3333-333333333333";
const char* BACKEND_HOST   = "10.173.247.138";
const int   BACKEND_PORT   = 8000;

// UART to CAM
#define CAM_UART_BAUD     115200
#define CAM_UART_RX_PIN   18
#define CAM_UART_TX_PIN   17

// Solenoid — disabled for current demo
#define ENABLE_SOLENOID     0
#define SOLENOID_PIN       10
#define SOLENOID_OPEN_MS  3000

// Timing and frame limits
#define HEADER_TIMEOUT_MS     30000
#define BODY_TIMEOUT_MS       10000
#define HTTP_TIMEOUT_MS       15000
#define MAX_FRAME_BYTES    (200 * 1024)
#define MIN_FRAME_BYTES        1024

// UART driver buffer is deliberately smaller than the JPEG frame buffer.
// receiveFrame() drains UART bytes into frameBuffer.
#define UART_RX_BUFFER_BYTES (16 * 1024)

// Maximum time spent draining a broken/partial frame before resynchronizing.
#define UART_RECOVERY_MAX_MS   3000
#define UART_RECOVERY_QUIET_MS   50

// ACK bytes
#define ACK_OK    0x4F
#define ACK_FAIL  0x46

uint8_t* frameBuffer = nullptr;
uint32_t receivedFrameCounter = 0;
String backendUrl;

// Backend outcome, as understood by the gateway.
enum ScanOutcome {
  OUTCOME_SUCCESS,          // HTTP 200 — ride confirmed
  OUTCOME_QR_NOT_FOUND,     // 422 DOCK_SCAN_QR_NOT_FOUND — no QR in this frame
  OUTCOME_TOKEN_REJECTED,   // QR decoded, token not acceptable (401/409)
  OUTCOME_FRAME_REJECTED,   // 413/415/422(other) — frame itself unusable
  OUTCOME_RATE_LIMITED,     // 429
  OUTCOME_TRANSPORT_FAILURE // no WiFi / timeout / connection error / 5xx
};

void triggerSolenoid() {
#if ENABLE_SOLENOID
  Serial.println("[LOCK] UNLOCKING solenoid...");
  digitalWrite(SOLENOID_PIN, HIGH);
  delay(SOLENOID_OPEN_MS);
  digitalWrite(SOLENOID_PIN, LOW);
  Serial.println("[LOCK] Solenoid closed");
#endif
}

uint8_t* allocateFrameBuffer() {
  if (psramFound()) {
    Serial.println("[MEM] QSPI PSRAM detected — allocating 200 KB frame buffer in PSRAM");
    return (uint8_t*)ps_malloc(MAX_FRAME_BYTES);
  }

  Serial.println("[MEM] WARNING: PSRAM not detected — falling back to internal heap");
  return (uint8_t*)malloc(MAX_FRAME_BYTES);
}

void recoverUartStream() {
  Serial.println("[UART] Recovering stream — draining stale bytes...");

  const unsigned long start = millis();
  unsigned long lastData = start;
  size_t drained = 0;

  while (millis() - start < UART_RECOVERY_MAX_MS) {
    bool gotData = false;

    while (Serial1.available()) {
      Serial1.read();
      drained++;
      gotData = true;
      lastData = millis();
    }

    if (!gotData && millis() - lastData >= UART_RECOVERY_QUIET_MS) {
      break;
    }

    delay(1);
  }

  Serial.printf(
    "[UART] Recovery complete — drained %u bytes\n",
    drained
  );
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("[WiFi] Connecting");

  const unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf(
      "\n[WiFi] Connected — IP: %s\n",
      WiFi.localIP().toString().c_str()
    );
  } else {
    Serial.println("\n[WiFi] FAILED — will retry when needed");
  }
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  Serial.println("[WiFi] Disconnected — reconnecting...");

  WiFi.reconnect();

  const unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(300);
  }

  return WiFi.status() == WL_CONNECTED;
}

size_t receiveFrame() {
  const uint32_t frameNumber = ++receivedFrameCounter;
  const unsigned long receiveStart = millis();

  uint8_t header[4] = {0};
  size_t headerBytes = 0;

  const unsigned long headerDeadline = millis() + HEADER_TIMEOUT_MS;

  while (
    headerBytes < 4 &&
    (long)(millis() - headerDeadline) < 0
  ) {
    if (Serial1.available()) {
      header[headerBytes++] = (uint8_t)Serial1.read();
    } else {
      delay(1);
    }
  }

  if (headerBytes < 4) {
    if (headerBytes > 0) {
      Serial.printf(
        "[S3][FRAME %lu] Partial header — got %u / 4 bytes; UART recovery\n",
        (unsigned long)frameNumber,
        headerBytes
      );
      recoverUartStream();
    }
    return 0;
  }

  const uint32_t frameLen =
      ((uint32_t)header[0] << 24)
    | ((uint32_t)header[1] << 16)
    | ((uint32_t)header[2] << 8)
    | ((uint32_t)header[3]);

  Serial.printf(
    "[S3][FRAME %lu] Header — expecting %u bytes\n",
    (unsigned long)frameNumber,
    frameLen
  );

  if (frameLen < MIN_FRAME_BYTES) {
    Serial.printf(
      "[S3][FRAME %lu] Too small (%u) — UART recovery\n",
      (unsigned long)frameNumber,
      frameLen
    );
    recoverUartStream();
    return 0;
  }

  if (frameLen > MAX_FRAME_BYTES) {
    Serial.printf(
      "[S3][FRAME %lu] Too large (%u) — UART recovery\n",
      (unsigned long)frameNumber,
      frameLen
    );
    recoverUartStream();
    return 0;
  }

  size_t received = 0;
  const unsigned long bodyStart = millis();
  unsigned long bodyDeadline = bodyStart + BODY_TIMEOUT_MS;

  while (
    received < frameLen &&
    (long)(millis() - bodyDeadline) < 0
  ) {
    const int avail = Serial1.available();

    if (avail > 0) {
      const size_t toRead =
        min((size_t)avail, (size_t)(frameLen - received));

      const size_t n =
        Serial1.readBytes(frameBuffer + received, toRead);

      received += n;

      // Only extend the deadline when bytes are actually arriving.
      bodyDeadline = millis() + BODY_TIMEOUT_MS;
    } else {
      delay(1);
    }
  }

  if (received < frameLen) {
    Serial.printf(
      "[S3][FRAME %lu] Body timeout — got %u / %u bytes (%lu ms)\n",
      (unsigned long)frameNumber,
      received,
      frameLen,
      millis() - bodyStart
    );

    recoverUartStream();
    return 0;
  }

  Serial.printf(
    "[S3][FRAME %lu] Complete — %u bytes in %lu ms\n",
    (unsigned long)frameNumber,
    received,
    millis() - receiveStart
  );

  return received;
}

// Pulls "code" out of {"success":false,"error":{"code":"...","message":"..."}}.
String extractErrorCode(const String& body) {
  const int key = body.indexOf("\"code\"");
  if (key < 0) return "";
  const int colon = body.indexOf(':', key);
  if (colon < 0) return "";
  const int q1 = body.indexOf('"', colon + 1);
  if (q1 < 0) return "";
  const int q2 = body.indexOf('"', q1 + 1);
  if (q2 < 0) return "";
  return body.substring(q1 + 1, q2);
}

ScanOutcome classifyResult(int httpCode, const String& errorCode) {
  if (httpCode == 200) return OUTCOME_SUCCESS;
  if (httpCode <= 0 || httpCode >= 500) return OUTCOME_TRANSPORT_FAILURE;
  if (httpCode == 429) return OUTCOME_RATE_LIMITED;
  if (errorCode == "DOCK_SCAN_QR_NOT_FOUND") return OUTCOME_QR_NOT_FOUND;
  if (httpCode == 401 || httpCode == 409) return OUTCOME_TOKEN_REJECTED;
  return OUTCOME_FRAME_REJECTED;
}

// Returns the HTTP status (or a negative HTTPClient error). On an error
// response, errorCode receives the backend's machine-readable code.
int postToBackend(size_t frameLen, String& errorCode) {
  const unsigned long start = millis();
  errorCode = "";

  if (!ensureWiFi()) {
    Serial.println("[HTTP] No WiFi — skipping frame");
    return -1;
  }

  Serial.printf(
    "[HTTP] POST start — %u bytes → %s\n",
    frameLen,
    backendUrl.c_str()
  );

  HTTPClient http;
  http.begin(backendUrl);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("Content-Length", String(frameLen));

  const int code = http.POST(frameBuffer, frameLen);

  if (code > 0) {
    const String body = http.getString();

    Serial.printf(
      "[HTTP] Response %d after %lu ms\n",
      code,
      millis() - start
    );

    Serial.printf("[HTTP] Body: %s\n", body.c_str());

    if (code != 200) {
      errorCode = extractErrorCode(body);
    }
  } else {
    Serial.printf(
      "[HTTP] Error after %lu ms: %s\n",
      millis() - start,
      http.errorToString(code).c_str()
    );
  }

  http.end();
  return code;
}

void sendAck(uint8_t ack) {
  Serial1.write(ack);
  Serial1.flush();
}

void handleScan() {
  const size_t frameLen = receiveFrame();

  if (frameLen == 0) {
    return;
  }

  const unsigned long scanStart = millis();
  String errorCode;
  const int httpCode = postToBackend(frameLen, errorCode);
  const ScanOutcome outcome = classifyResult(httpCode, errorCode);

  Serial.printf(
    "[SCAN] Frame processing path: %lu ms\n",
    millis() - scanStart
  );

  switch (outcome) {
    case OUTCOME_SUCCESS:
      sendAck(ACK_OK);
#if ENABLE_SOLENOID
      Serial.println("[SCAN] SUCCESS — ride confirmed; triggering solenoid");
      triggerSolenoid();
#else
      Serial.println("[SCAN] SUCCESS — ride confirmed; solenoid DISABLED");
#endif
      return;

    case OUTCOME_QR_NOT_FOUND:
      Serial.println("[SCAN] QR not found in this frame — ACK_FAIL (camera should retry)");
      break;

    case OUTCOME_TOKEN_REJECTED:
      // Includes RIDE_TOKEN_EXPIRED / INVALID / REUSED, RIDE_DOCK_MISMATCH,
      // VEHICLE_UNAVAILABLE. Not a camera fault. The 1-byte ACK cannot say so.
      Serial.printf(
        "[SCAN] QR read but token rejected (HTTP %d, %s) — ACK_FAIL\n",
        httpCode,
        errorCode.length() ? errorCode.c_str() : "no code"
      );
      break;

    case OUTCOME_FRAME_REJECTED:
      Serial.printf(
        "[SCAN] Frame rejected by backend (HTTP %d, %s) — ACK_FAIL\n",
        httpCode,
        errorCode.length() ? errorCode.c_str() : "no code"
      );
      break;

    case OUTCOME_RATE_LIMITED:
      Serial.println("[SCAN] Backend rate limit (429) — ACK_FAIL");
      break;

    case OUTCOME_TRANSPORT_FAILURE:
      Serial.printf(
        "[SCAN] Transport/backend failure (%d) — not a QR problem — ACK_FAIL\n",
        httpCode
      );
      break;
  }

  sendAck(ACK_FAIL);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n[VELO-S3] Gateway booting...");
  Serial.printf(
    "[MEM] PSRAM detected at boot: %s\n",
    psramFound() ? "YES" : "NO"
  );

#if ENABLE_SOLENOID
  pinMode(SOLENOID_PIN, OUTPUT);
  digitalWrite(SOLENOID_PIN, LOW);
#else
  Serial.println("[LOCK] Solenoid path DISABLED for current demo");
#endif

  // Keep UART driver buffer much smaller than the JPEG frame buffer.
  Serial1.setRxBufferSize(UART_RX_BUFFER_BYTES);

  Serial1.begin(
    CAM_UART_BAUD,
    SERIAL_8N1,
    CAM_UART_RX_PIN,
    CAM_UART_TX_PIN
  );

  Serial.printf(
    "[UART] Serial1 up at %d baud (RX=GPIO%d TX=GPIO%d)\n",
    CAM_UART_BAUD,
    CAM_UART_RX_PIN,
    CAM_UART_TX_PIN
  );

  frameBuffer = allocateFrameBuffer();

  if (!frameBuffer) {
    Serial.println(
      "[VELO-S3] FATAL: frame buffer allocation failed — halting"
    );

    while (true) {
      delay(1000);
    }
  }

  Serial.printf(
    "[VELO-S3] Frame buffer: %u KB\n",
    MAX_FRAME_BYTES / 1024
  );

  Serial.printf(
    "[VELO-S3] UART RX buffer: %u KB\n",
    UART_RX_BUFFER_BYTES / 1024
  );

  backendUrl =
    String("http://")
    + BACKEND_HOST
    + ":"
    + BACKEND_PORT
    + "/api/v1/docks/"
    + DOCK_ID
    + "/scan";

  Serial.printf(
    "[VELO-S3] Backend URL: %s\n",
    backendUrl.c_str()
  );

  connectWiFi();

  Serial.println(
    "[VELO-S3] Ready — waiting for frames from CAM"
  );
}

void loop() {
  handleScan();
}
