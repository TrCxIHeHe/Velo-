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
const char* BACKEND_HOST   = "10.242.1.138";
const int   BACKEND_PORT   = 8000;

// UART to CAM
#define CAM_UART_BAUD     921600
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

int postToBackend(size_t frameLen) {
  const unsigned long start = millis();

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

void handleScan() {
  const size_t frameLen = receiveFrame();

  if (frameLen == 0) {
    return;
  }

  const unsigned long scanStart = millis();
  const int httpCode = postToBackend(frameLen);

  Serial.printf(
    "[SCAN] Frame processing path: %lu ms\n",
    millis() - scanStart
  );

  if (httpCode == 200) {
    Serial1.write(ACK_OK);
    Serial1.flush();

#if ENABLE_SOLENOID
    Serial.println("[SCAN] SUCCESS — ride confirmed; triggering solenoid");
    triggerSolenoid();
#else
    Serial.println("[SCAN] SUCCESS — ride confirmed; solenoid DISABLED");
#endif
    return;
  }

  if (httpCode == 422) {
    Serial.println(
      "[SCAN] QR not decoded in this frame — sending FAIL"
    );
    Serial1.write(ACK_FAIL);
    Serial1.flush();
    return;
  }

  if (httpCode == 409 || httpCode == 410) {
    Serial.printf(
      "[SCAN] Token rejected (%d) — sending FAIL\n",
      httpCode
    );
    Serial1.write(ACK_FAIL);
    Serial1.flush();
    return;
  }

  Serial.printf(
    "[SCAN] HTTP/network failure (%d) — sending FAIL\n",
    httpCode
  );

  Serial1.write(ACK_FAIL);
  Serial1.flush();
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
