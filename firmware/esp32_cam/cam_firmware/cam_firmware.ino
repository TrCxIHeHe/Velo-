/**
 * Velo — ESP32-CAM Firmware (Option A: capture-only node)
 * Board  : AI Thinker ESP32-CAM
 * Camera : OV2640 (JPEG, QVGA 320×240)
 * Role   : Capture JPEG frames every ~3.5 s → send to ESP32-S3 over UART
 *          → wait for final scan ACK from the S3/backend
 *
 * What this chip does NOT do:
 *   - No WiFi stack
 *   - No HTTPClient
 *   - No solenoid logic
 *
 * Wiring:
 *   Programming (FTDI — only during flash):
 *     FTDI TX  → ESP32-CAM GPIO3 (U0RXD)
 *     FTDI RX  → ESP32-CAM GPIO1 (U0TXD)
 *     FTDI GND → ESP32-CAM GND
 *     GPIO0    → GND only while flashing
 *
 *   Power:
 *     External 5V PSU → ESP32-CAM 5V & GND
 *
 *   UART link to S3:
 *     ESP32-CAM GPIO12 (TX) → ESP32-S3 GPIO18 (RX)
 *     ESP32-CAM GPIO13 (RX) ← ESP32-S3 GPIO17 (TX)
 *     Shared GND
 *
 * Frame wire protocol:
 *   CAM → S3 : [4 bytes big-endian uint32 length] [length bytes JPEG]
 *   S3  → CAM: [1 byte ACK]
 *              0x4F ('O') = success
 *              0x46 ('F') = frame rejected / retry
 *
 * Arduino IDE:
 *   Board : AI Thinker ESP32-CAM
 *   Upload Speed : 115200
 */

#include "esp_camera.h"

// Camera pin map — AI Thinker ESP32-CAM
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

// UART link to S3
#define S3_UART_BAUD     921600
#define S3_UART_TX_PIN    12
#define S3_UART_RX_PIN    13

// Feedback
#define LED_PIN            4

// Timing
#define CAPTURE_INTERVAL_MS  3500   // Fresh frame about every 3.5 s
#define RETRY_DELAY_MS       4000   // Delay before retrying a rejected frame
#define ACK_TIMEOUT_MS      35000   // Maximum wait for S3/backend result
#define MAX_SCAN_RETRIES        3
#define CHUNK_SIZE            512
#define DUMMY_FRAMES           10

// ACK bytes
#define ACK_OK    0x4F
#define ACK_FAIL  0x46

bool cameraReady = false;
uint32_t captureCounter = 0;

void blinkCapture() {
  digitalWrite(LED_PIN, HIGH);
  delay(60);
  digitalWrite(LED_PIN, LOW);
}

void blinkSuccess() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(80);
    digitalWrite(LED_PIN, LOW);
    delay(80);
  }
}

void blinkError() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(180);
    digitalWrite(LED_PIN, LOW);
    delay(180);
  }
}

bool initCamera() {
  camera_config_t cfg={};
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
  cfg.sccb_i2c_port=0;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;

  // Conservative QR-demo configuration.
  cfg.frame_size   = FRAMESIZE_QVGA;
  cfg.jpeg_quality = 12;
  cfg.fb_count     = 1;
  cfg.fb_location  = CAMERA_FB_IN_DRAM;

  esp_err_t err = ESP_FAIL;
  for (int i = 0; i < 3; i++) {
    err = esp_camera_init(&cfg);
    if (err == ESP_OK) {
      Serial.println("[CAM] Camera init OK");
      break;
    }

    Serial.printf("[CAM] Init attempt %d failed: 0x%x\n", i + 1, err);
    esp_camera_deinit();
    delay(500);
  }

  if (err != ESP_OK) {
    Serial.println("[CAM] Camera init FAILED — check camera and power wiring");
    return false;
  }

  Serial.print("[CAM] Settling");
  for (int i = 0; i < DUMMY_FRAMES; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
      esp_camera_fb_return(fb);
    }
    delay(50);
    Serial.print(".");
  }
  Serial.println(" done");

  return true;
}

void clearPendingAcks() {
  while (Serial2.available()) {
    Serial2.read();
  }
}

uint8_t captureAndSend() {
  const uint32_t frameId = ++captureCounter;
  const unsigned long totalStart = millis();

  // Remove any delayed/stale ACK from an earlier failed cycle.
  clearPendingAcks();

  Serial.printf("\n[CAM][FRAME %lu] Capturing...\n", (unsigned long)frameId);

  const unsigned long captureStart = millis();
  camera_fb_t* fb = esp_camera_fb_get();
  const unsigned long captureMs = millis() - captureStart;

  if (!fb) {
    Serial.printf("[CAM][FRAME %lu] Capture FAILED after %lu ms\n",
                  (unsigned long)frameId, captureMs);
    blinkError();
    return 0x00;
  }

  const size_t len = fb->len;

  Serial.printf("[CAM][FRAME %lu] Captured: %u bytes, %dx%d, %lu ms\n",
                (unsigned long)frameId,
                len,
                fb->width,
                fb->height,
                captureMs);

  const unsigned long uartStart = millis();

  uint8_t header[4] = {
    (uint8_t)(len >> 24),
    (uint8_t)(len >> 16),
    (uint8_t)(len >> 8),
    (uint8_t)len
  };

  if (Serial2.write(header, 4) != 4) {
    Serial.printf("[CAM][FRAME %lu] Failed to write UART header\n",
                  (unsigned long)frameId);
    esp_camera_fb_return(fb);
    blinkError();
    clearPendingAcks();
    return 0x00;
  }

  size_t sent = 0;

  while (sent < len) {
    const size_t chunk = min((size_t)CHUNK_SIZE, len - sent);
    const size_t written = Serial2.write(fb->buf + sent, chunk);

    if (written != chunk) {
      Serial.printf("[CAM][FRAME %lu] UART short write: %u/%u bytes\n",
                    (unsigned long)frameId,
                    written,
                    chunk);
      esp_camera_fb_return(fb);
      blinkError();
      clearPendingAcks();
      return 0x00;
    }

    sent += written;
  }

  Serial2.flush();
  const unsigned long uartMs = millis() - uartStart;

  esp_camera_fb_return(fb);
  blinkCapture();

  Serial.printf("[CAM][FRAME %lu] Sent %u bytes in %lu ms\n",
                (unsigned long)frameId,
                len,
                uartMs);

  Serial.printf("[CAM][FRAME %lu] Waiting for ACK (max %lu s)...\n",
                (unsigned long)frameId,
                (unsigned long)(ACK_TIMEOUT_MS / 1000));

  const unsigned long ackStart = millis();
  const unsigned long deadline = ackStart + ACK_TIMEOUT_MS;

  while ((long)(millis() - deadline) < 0) {
    if (Serial2.available()) {
      const uint8_t ack = (uint8_t)Serial2.read();
      const unsigned long ackWaitMs = millis() - ackStart;
      const unsigned long totalMs = millis() - totalStart;

      Serial.printf(
        "[CAM][FRAME %lu] ACK 0x%02X (%c) after %lu ms; total %lu ms\n",
        (unsigned long)frameId,
        ack,
        (ack >= 0x20 && ack <= 0x7E) ? ack : '?',
        ackWaitMs,
        totalMs
      );

      return ack;
    }

    delay(10);
  }

  Serial.printf("[CAM][FRAME %lu] ACK TIMEOUT after %lu ms\n",
                (unsigned long)frameId,
                millis() - ackStart);

  clearPendingAcks();
  blinkError();
  return 0x00;
}

void scanWithRetry() {
  for (int attempt = 0; attempt < MAX_SCAN_RETRIES; attempt++) {
    if (attempt > 0) {
      Serial.printf("[SCAN] Retry %d/%d after %lu ms\n",
                    attempt + 1,
                    MAX_SCAN_RETRIES,
                    (unsigned long)RETRY_DELAY_MS);
      delay(RETRY_DELAY_MS);
    }

    const uint8_t ack = captureAndSend();

    if (ack == ACK_OK) {
      Serial.println("[SCAN] SUCCESS — valid ride QR confirmed by backend");
      blinkSuccess();
      return;
    }

    if (ack == ACK_FAIL) {
      Serial.println(
        "[SCAN] FAIL — backend did not accept this frame; retrying with fresh capture"
      );
      continue;
    }

    Serial.println("[SCAN] TIMEOUT / UART ERROR — aborting current scan cycle");
    return;
  }

  Serial.println("[SCAN] Retries exhausted — backing off");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n[VELO-CAM] Booting...");

  Serial2.begin(
    S3_UART_BAUD,
    SERIAL_8N1,
    S3_UART_RX_PIN,
    S3_UART_TX_PIN
  );

  Serial.printf(
    "[UART] Serial2 up at %d baud (TX=GPIO%d RX=GPIO%d)\n",
    S3_UART_BAUD,
    S3_UART_TX_PIN,
    S3_UART_RX_PIN
  );

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  cameraReady = initCamera();

  Serial.println(
    cameraReady
      ? "[VELO-CAM] Ready — captures every ~3.5 s"
      : "[VELO-CAM] Camera fault"
  );
}

void loop() {
  if (!cameraReady) {
    Serial.println("[VELO-CAM] Retrying camera init...");
    cameraReady = initCamera();
    delay(3000);
    return;
  }

  scanWithRetry();

  Serial.printf(
    "[CAM] Next scan cycle in %lu ms\n",
    (unsigned long)CAPTURE_INTERVAL_MS
  );

  delay(CAPTURE_INTERVAL_MS);
}