#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_heap_caps.h"

#define OLED_WIDTH 128
#define OLED_HEIGHT 64
#define OLED_SDA 13
#define OLED_SCL 14

// AI Thinker ESP32-CAM camera pin map.
#define CAMERA_PWDN 32
#define CAMERA_RESET -1
#define CAMERA_XCLK 0
#define CAMERA_SIOD 26
#define CAMERA_SIOC 27
#define CAMERA_Y9 35
#define CAMERA_Y8 34
#define CAMERA_Y7 39
#define CAMERA_Y6 36
#define CAMERA_Y5 21
#define CAMERA_Y4 19
#define CAMERA_Y3 18
#define CAMERA_Y2 5
#define CAMERA_VSYNC 25
#define CAMERA_HREF 23
#define CAMERA_PCLK 22

const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *SERVER_URL = "http://192.168.1.10:5050/predict";
const char *MULTIPART_BOUNDARY = "AgriTechCameraBoundary";
const unsigned long SCAN_INTERVAL_MS = 30000;

Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);

void showMessage(const String &heading, const String &message) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextWrap(true);
  display.setCursor(0, 0);
  display.println(heading);
  display.println();
  display.println(message);
  display.display();
}

bool startCamera() {
  camera_config_t cameraConfig = {};
  cameraConfig.ledc_channel = LEDC_CHANNEL_0;
  cameraConfig.ledc_timer = LEDC_TIMER_0;
  cameraConfig.pin_d0 = CAMERA_Y2;
  cameraConfig.pin_d1 = CAMERA_Y3;
  cameraConfig.pin_d2 = CAMERA_Y4;
  cameraConfig.pin_d3 = CAMERA_Y5;
  cameraConfig.pin_d4 = CAMERA_Y6;
  cameraConfig.pin_d5 = CAMERA_Y7;
  cameraConfig.pin_d6 = CAMERA_Y8;
  cameraConfig.pin_d7 = CAMERA_Y9;
  cameraConfig.pin_xclk = CAMERA_XCLK;
  cameraConfig.pin_pclk = CAMERA_PCLK;
  cameraConfig.pin_vsync = CAMERA_VSYNC;
  cameraConfig.pin_href = CAMERA_HREF;
  cameraConfig.pin_sccb_sda = CAMERA_SIOD;
  cameraConfig.pin_sccb_scl = CAMERA_SIOC;
  cameraConfig.pin_pwdn = CAMERA_PWDN;
  cameraConfig.pin_reset = CAMERA_RESET;
  cameraConfig.xclk_freq_hz = 20000000;
  cameraConfig.pixel_format = PIXFORMAT_JPEG;
  cameraConfig.frame_size = FRAMESIZE_VGA;
  cameraConfig.jpeg_quality = 12;
  cameraConfig.fb_count = 1;
  cameraConfig.fb_location = CAMERA_FB_IN_PSRAM;
  cameraConfig.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  return esp_camera_init(&cameraConfig) == ESP_OK;
}

void captureAndDiagnose() {
  showMessage("AgriTech", "Capturing leaf image...");
  camera_fb_t *frame = esp_camera_fb_get();
  if (frame == nullptr) {
    showMessage("Camera error", "Could not capture image. Check camera connection.");
    return;
  }

  String prefix = "--";
  prefix += MULTIPART_BOUNDARY;
  prefix += "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"leaf.jpg\"\r\n";
  prefix += "Content-Type: image/jpeg\r\n\r\n";
  String suffix = "\r\n--";
  suffix += MULTIPART_BOUNDARY;
  suffix += "--\r\n";

  const size_t bodyLength = prefix.length() + frame->len + suffix.length();
  uint8_t *body = static_cast<uint8_t *>(
      heap_caps_malloc(bodyLength, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (body == nullptr) {
    body = static_cast<uint8_t *>(malloc(bodyLength));
  }
  if (body == nullptr) {
    esp_camera_fb_return(frame);
    showMessage("Memory error", "Could not prepare image upload.");
    return;
  }

  size_t offset = 0;
  memcpy(body + offset, prefix.c_str(), prefix.length());
  offset += prefix.length();
  memcpy(body + offset, frame->buf, frame->len);
  offset += frame->len;
  memcpy(body + offset, suffix.c_str(), suffix.length());
  esp_camera_fb_return(frame);

  showMessage("AgriTech", "Sending image to local model...");
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(30000);
  if (!http.begin(client, SERVER_URL)) {
    free(body);
    showMessage("Network error", "Could not reach the Flask server.");
    return;
  }

  String contentType = "multipart/form-data; boundary=";
  contentType += MULTIPART_BOUNDARY;
  http.addHeader("Content-Type", contentType);
  const int statusCode = http.POST(body, bodyLength);
  free(body);

  String response = http.getString();
  http.end();
  if (statusCode < 200 || statusCode >= 300) {
    showMessage("Prediction error", "HTTP " + String(statusCode) + "\n" + response.substring(0, 90));
    Serial.println(response);
    return;
  }

  DynamicJsonDocument result(4096);
  DeserializationError error = deserializeJson(result, response);
  if (error) {
    showMessage("Response error", "Could not read model result.");
    Serial.println(response);
    return;
  }

  const char *disease = result["disease"] | "Unknown disease";
  const float confidence = result["confidence"] | 0.0f;
  String diagnosis = String(disease) + "\nConfidence: ";
  diagnosis += String(confidence * 100.0f, 1);
  diagnosis += "%";
  showMessage("Diagnosis", diagnosis);
  Serial.println(diagnosis);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found. Check SDA/SCL wiring.");
    while (true) delay(1000);
  }
  showMessage("AgriTech", "Starting camera...");

  if (!psramFound()) {
    showMessage("PSRAM required", "Use an AI Thinker ESP32-CAM with PSRAM.");
    while (true) delay(1000);
  }
  if (!startCamera()) {
    showMessage("Camera error", "Camera initialization failed.");
    while (true) delay(1000);
  }

  showMessage("AgriTech", "Connecting to Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    showMessage("Wi-Fi", "Reconnecting...");
    WiFi.reconnect();
    delay(5000);
    return;
  }
  captureAndDiagnose();
  delay(SCAN_INTERVAL_MS);
}
