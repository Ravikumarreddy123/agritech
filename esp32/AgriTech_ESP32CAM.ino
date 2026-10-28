/**
 * AgriTech — ESP32-CAM Plant Disease Detector
 * =============================================
 * Hardware:
 *   - ESP32-CAM (AI-Thinker board with OV2640 camera)
 *   - 0.96" OLED Display I2C (128x64, SSD1306)
 *   - Push button on GPIO 13 (optional — triggers capture)
 *
 * Wiring (OLED to ESP32-CAM):
 *   VCC  → 3.3V
 *   GND  → GND
 *   SCL  → GPIO 14  (use 14 on AI-Thinker — GPIO22 is used by flash LED)
 *   SDA  → GPIO 15
 *
 * Libraries Required (install via Arduino Library Manager):
 *   - Adafruit SSD1306
 *   - Adafruit GFX
 *   - ArduinoJson  (v6.x)
 *   - ESP32 board support (Espressif Systems)
 *
 * Board Settings:
 *   Board: "AI Thinker ESP32-CAM"
 *   Upload Speed: 115200
 *   Flash Mode: QIO
 *   Partition Scheme: Huge APP (3MB No OTA)
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ─── USER CONFIGURATION ────────────────────────────────────────────────
// 1. Set your Wi-Fi credentials
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 2. Set your laptop/PC IP (find it with: ipconfig → IPv4 Address)
//    The Flask app must be running on port 5050
const char* SERVER_URL = "http://192.168.22.10:5050/esp32/predict";

// 3. Capture button pin (press to take photo)
const int BUTTON_PIN = 13;
// ───────────────────────────────────────────────────────────────────────

// ─── OLED Display ──────────────────────────────────────────────────────
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_SDA 15
#define OLED_SCL 14
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ─── AI-Thinker ESP32-CAM Pin Map ──────────────────────────────────────
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

// ─── Setup ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // OLED init
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ERROR] OLED not found!");
  }
  oledShow("AgriTech", "Starting...", "", "");

  // Camera init
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;  // 320x240 — good balance
  config.jpeg_quality = 12;              // 0-63, lower = better quality
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Camera init failed: 0x%x\n", err);
    oledShow("Camera Error!", "Check wiring", "", "");
    while (true) delay(1000);
  }
  Serial.println("[OK] Camera ready.");

  // Wi-Fi connect
  oledShow("AgriTech", "Connecting", "to WiFi...", "");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[OK] WiFi connected: %s\n", WiFi.localIP().toString().c_str());
    oledShow("WiFi OK!", WiFi.localIP().toString().c_str(), "Press button", "to scan leaf");
  } else {
    Serial.println("\n[ERROR] WiFi failed!");
    oledShow("WiFi Failed!", "Check SSID &", "Password", "");
  }
}

// ─── Main Loop ─────────────────────────────────────────────────────────
void loop() {
  // Wait for button press (LOW when pressed, because INPUT_PULLUP)
  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(200);  // debounce

    oledShow("Capturing...", "Hold leaf", "still!", "");
    delay(500);

    // Capture photo
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("[ERROR] Camera capture failed");
      oledShow("Capture", "Failed!", "Try again.", "");
      delay(2000);
      return;
    }
    Serial.printf("[OK] Photo captured: %u bytes\n", fb->len);
    oledShow("Sending...", "Analysing", "leaf...", "");

    // Send to Flask and get result
    String disease = "", risk = "", conf = "";
    bool success = sendToFlask(fb->buf, fb->len, disease, conf, risk);

    // Return frame buffer
    esp_camera_fb_return(fb);

    if (success) {
      Serial.printf("[RESULT] %s | %s%% | %s\n", disease.c_str(), conf.c_str(), risk.c_str());
      // Show on OLED — up to 4 lines
      String line2 = disease.length() > 21 ? disease.substring(0, 21) : disease;
      String line3 = disease.length() > 21 ? disease.substring(21, min((int)disease.length(), 42)) : "";
      String line4 = "Conf:" + conf + "% " + risk;
      oledShow("Disease:", line2, line3, line4);
    } else {
      oledShow("Error!", "No response", "Check server", "& WiFi");
    }

    delay(5000);  // show result for 5 seconds
    oledShow("Ready!", "Press button", "to scan", "leaf");
  }
  delay(100);
}

// ─── Send Image to Flask Server ────────────────────────────────────────
bool sendToFlask(uint8_t* imgData, size_t imgLen,
                 String& disease, String& conf, String& risk) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ERROR] WiFi disconnected!");
    return false;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "image/jpeg");
  http.setTimeout(15000);  // 15 second timeout (model inference takes ~2s)

  Serial.printf("[HTTP] Sending %u bytes to %s\n", imgLen, SERVER_URL);
  int httpCode = http.POST(imgData, imgLen);
  Serial.printf("[HTTP] Response code: %d\n", httpCode);

  if (httpCode != 200) {
    http.end();
    return false;
  }

  String payload = http.getString();
  http.end();
  Serial.println("[HTTP] Response: " + payload);

  // Parse JSON: {"disease": "...", "confidence": 92.1, "risk": "HIGH", ...}
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.println("[ERROR] JSON parse failed: " + String(err.c_str()));
    return false;
  }

  disease = doc["disease"].as<String>();
  conf    = String(doc["confidence"].as<float>(), 1);
  risk    = doc["risk"].as<String>();
  return true;
}

// ─── OLED Display Helper ───────────────────────────────────────────────
void oledShow(const char* line1, const char* line2,
              const char* line3, const char* line4) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(line1);

  display.setCursor(0, 16);
  display.println(line2);

  display.setCursor(0, 32);
  display.println(line3);

  display.setCursor(0, 48);
  display.println(line4);

  display.display();
}

void oledShow(const char* line1, String line2,
              String line3, String line4) {
  oledShow(line1, line2.c_str(), line3.c_str(), line4.c_str());
}
