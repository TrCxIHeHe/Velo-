/**
 * Velo — ESP32-CAM Firmware (Option A: capture-only node)
 * ─────────────────────────────────────────────────────────────────────────────
 * Board  : AI Thinker ESP32-CAM
 * Camera : OV2640  (JPEG, VGA 640×480)
 * Role   : Capture JPEG frames → send to ESP32-S3 over UART → receive ACK
 *
 * What this chip does NOT do:
 *   - No WiFi stack (saves ~270 KB IRAM + removes contention with camera DMA)
 *   - No HTTPClient
 *   - No solenoid logic
 *
 * All networking is offloaded to the ESP32-S3 (see esp32_s3/s3_gateway.ino).
 *
 * ── Wiring ───────────────────────────────────────────────────────────────────
 *  Programming (FTDI — only during flash):
 *    FTDI TX  → ESP32-CAM GPIO3 (U0RXD)
 *    FTDI RX  → ESP32-CAM GPIO1 (U0TXD)
 *    FTDI GND → ESP32-CAM GND
 *    GPIO0    → GND  (boot mode — remove after flashing, press RST)
 *
 *  Power:
 *    External 5V PSU → ESP32-CAM 5V & GND
 *
 *  UART link to S3 (Serial2):
 *    ESP32-CAM GPIO12 (TX) → ESP32-S3 GPIO18 (RX)   [921600 baud]
 *    ESP32-CAM GPIO13 (RX) ← ESP32-S3 GPIO17 (TX)   [ACK byte]
 *    Shared GND rail
 *
 *  NOTE: GPIO12 (MTDI) and GPIO13 (MTCK) are PSRAM SPI pins on this module.
 *  Repurposing them as UART means psramFound() returns false → the camera
 *  falls back to QVGA/DRAM (320×240), which is plenty for QR decode.
 *  If you ever need VGA + PSRAM: use GPIO14/GPIO15 for UART instead and
 *  update the matching S3 pin defines.
 *
 * ── Frame wire protocol ───────────────────────────────────────────────────────
 *  CAM → S3  : [4 bytes big-endian uint32 length] [length bytes JPEG]
 *  S3  → CAM : [1 byte ACK]  0x4F ('O') = success  |  0x46 ('F') = retry
 *
 * ── Arduino IDE settings ─────────────────────────────────────────────────────
 *   Board   : "AI Thinker ESP32-CAM"
 *   Port    : COMx (FTDI port)
 *   Upload Speed: 115200
 *   After upload: remove GPIO0-GND wire, press RST
 * ─────────────────────────────────────────────────────────────────────────────
 */

#include "esp_camera.h"

// ── Camera pin map — AI Thinker ESP32-CAM ─────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ── UART link to S3 ────────────────────────────────────────────────────────────
#define S3_UART_BAUD     921600
#define S3_UART_TX_PIN    12   // → S3 GPIO18
#define S3_UART_RX_PIN    13   // ← S3 GPIO17 (ACK)

// ── Feedback ───────────────────────────────────────────────────────────────────
#define LED_PIN            4   // On-board flash LED

// ── Timing ────────────────────────────────────────────────────────────────────
#define CAPTURE_INTERVAL_MS   500   // Scan interval when idle
#define ACK_TIMEOUT_MS       20000  // Wait up to 20 s for S3 to POST + reply
#define MAX_SCAN_RETRIES        3   // Retries on 'F' ACK before backing off
#define CHUNK_SIZE            512   // UART write chunk (bytes) — prevents TX FIFO overrun
#define DUMMY_FRAMES           10   // OV2640 AEC/AWB settling frames

// ── ACK bytes (must match s3_gateway.ino) ─────────────────────────────────────
#define ACK_OK    0x4F   // 'O'
#define ACK_FAIL  0x46   // 'F'

// ── State ─────────────────────────────────────────────────────────────────────
bool cameraReady = false;

// ══════════════════════════════════════════════════════════════════════════════
// Camera init
// ══════════════════════════════════════════════════════════════════════════════
bool initCamera() {
  camera_config_t cfg;
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_d0       = Y2_GPIO_NUM;
  cfg.pin_d1       = Y3_GPIO_NUM;
  cfg.pin_d2       = Y4_GPIO_NUM;
  cfg.pin_d3       = Y5_GPIO_NUM;
  cfg.pin_d4       = Y6_GPIO_NUM;
  cfg.pin_d5       = Y7_GPIO_NUM;
  cfg.pin_d6       = Y8_GPIO_NUM;
  cfg.pin_d7       = Y9_GPIO_NUM;
  cfg.pin_xclk     = XCLK_GPIO_NUM;
  cfg.pin_pclk     = PCLK_GPIO_NUM;
  cfg.pin_vsync    = VSYNC_GPIO_NUM;
  cfg.pin_href     = HREF_GPIO_NUM;
  cfg.pin_sccb_sda = SIOD_GPIO_NUM;
  cfg.pin_sccb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn     = PWDN_GPIO_NUM;
  cfg.pin_reset    = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;

  // GPIO12/13 are repurposed as UART → PSRAM unavailable → QVGA in DRAM.
  // QVGA (320×240) is sufficient for QR decode and keeps frame size ~15–25 KB,
  // well within the 200 KB backend limit and fast over 921600 baud (~0.2 s).
  cfg.frame_size   = FRAMESIZE_QVGA;
  cfg.jpeg_quality = 12;
  cfg.fb_count     = 1;
  cfg.fb_location  = CAMERA_FB_IN_DRAM;

  esp_err_t err = ESP_FAIL;
  for (int i = 0; i < 3; i++) {
    err = esp_camera_init(&cfg);
    if (err == ESP_OK) { Serial.println("[CAM] Init OK"); break; }
    Serial.printf("[CAM] Init attempt %d failed: 0x%x\n", i + 1, err);
    esp_camera_deinit();
    delay(500);
  }
  if (err != ESP_OK) { Serial.println("[CAM] Init FAILED — check wiring"); return false; }

  // Flush dummy frames so AEC/AWB settle
  Serial.print("[CAM] Settling");
  for (int i = 0; i < DUMMY_FRAMES; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    delay(50);
    Serial.print(".");
  }
  Serial.println(" done");
  return true;
}

// ══════════════════════════════════════════════════════════════════════════════
// Send one JPEG frame to S3 and wait for ACK
//
// Returns:
//   ACK_OK   (0x4F) — S3 confirmed ride, solenoid triggered
//   ACK_FAIL (0x46) — S3 couldn't decode or backend error, retry
//   0x00            — capture/UART error
// ══════════════════════════════════════════════════════════════════════════════
uint8_t captureAndSend() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] Frame capture NULL");
    return 0x00;
  }

  size_t len = fb->len;
  Serial.printf("[CAM] Frame %u bytes (%dx%d)\n", len, fb->width, fb->height);

  // ── Send 4-byte big-endian length header ──────────────────────────────────
  uint8_t header[4] = {
    (uint8_t)(len >> 24),
    (uint8_t)(len >> 16),
    (uint8_t)(len >>  8),
    (uint8_t)(len      )
  };
  Serial2.write(header, 4);
  Serial2.flush();

  // ── Send JPEG in chunks (prevents TX FIFO stalls) ─────────────────────────
  size_t sent = 0;
  while (sent < len) {
    size_t chunk = min((size_t)CHUNK_SIZE, len - sent);
    Serial2.write(fb->buf + sent, chunk);
    sent += chunk;
  }
  Serial2.flush();
  esp_camera_fb_return(fb);   // Return buffer immediately after send

  Serial.printf("[UART] Sent %u bytes — waiting for ACK...\n", len);

  // ── Wait for 1-byte ACK ───────────────────────────────────────────────────
  unsigned long deadline = millis() + ACK_TIMEOUT_MS;
  while (millis() < deadline) {
    if (Serial2.available()) {
      uint8_t ack = (uint8_t)Serial2.read();
      Serial.printf("[UART] ACK: 0x%02X (%c)\n", ack, (ack >= 0x20) ? ack : '?');
      return ack;
    }
    delay(10);
  }
  Serial.println("[UART] ACK timeout");
  return 0x00;
}

// ══════════════════════════════════════════════════════════════════════════════
// Scan loop with retries
// ══════════════════════════════════════════════════════════════════════════════
void scanWithRetry() {
  for (int attempt = 0; attempt < MAX_SCAN_RETRIES; attempt++) {
    if (attempt > 0) {
      Serial.printf("[SCAN] Retry %d/%d\n", attempt + 1, MAX_SCAN_RETRIES);
      delay(400);
    }

    uint8_t ack = captureAndSend();

    if (ack == ACK_OK) {
      Serial.println("[SCAN] ✅ Ride confirmed — S3 is triggering solenoid");
      // Visual feedback: fast blink LED 3×
      for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, HIGH); delay(80);
        digitalWrite(LED_PIN, LOW);  delay(80);
      }
      delay(3000);   // Cool-down: don't scan again until solenoid closes
      return;
    }

    if (ack == ACK_FAIL) {
      // S3 sent explicit fail: QR not decoded or backend returned 422/4xx
      // Retry with a fresh capture (better angle / lighting)
      Serial.println("[SCAN] ⚠️  S3 returned FAIL — retrying capture");
      continue;
    }

    // Timeout or 0x00 — UART or capture issue
    Serial.println("[SCAN] ❌ No ACK received — UART or S3 issue");
    return;
  }
  Serial.println("[SCAN] Retries exhausted — backing off");
}

// ══════════════════════════════════════════════════════════════════════════════
// setup() / loop()
// ══════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);   // Debug via FTDI (GPIO1/3)
  delay(200);
  Serial.println("\n[VELO-CAM] Booting...");

  // UART2 to S3 — TX=GPIO12, RX=GPIO13
  Serial2.begin(S3_UART_BAUD, SERIAL_8N1, S3_UART_RX_PIN, S3_UART_TX_PIN);
  Serial.printf("[UART] Serial2 up at %d baud (TX=GPIO%d RX=GPIO%d)\n",
                S3_UART_BAUD, S3_UART_TX_PIN, S3_UART_RX_PIN);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  cameraReady = initCamera();
  Serial.println(cameraReady ? "[VELO-CAM] Ready — scanning" : "[VELO-CAM] Camera fault");
}

void loop() {
  if (!cameraReady) {
    Serial.println("[VELO-CAM] Retrying camera init...");
    cameraReady = initCamera();
    delay(3000);
    return;
  }
  scanWithRetry();
  delay(CAPTURE_INTERVAL_MS);
}
