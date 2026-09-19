#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <esp_mac.h>

// =============================================================================
// Configuration Constants
// =============================================================================
// Dedicated local transport network hosted directly by the laptop (2.4 GHz, no AP isolation)
const char* WIFI_SSID     = "KUSH-PC 3059";
const char* WIFI_PASSWORD = "08c0C92%";
const char* BACKEND_HOST  = "192.168.137.1";
const int   BACKEND_PORT  = 8000;
const char* POD_ID        = "pod_c";

// Delay between successive scan/ingest cycles (ms)
const unsigned long CYCLE_DELAY_MS = 2500;

static unsigned long scanCycle = 0;

// =============================================================================
// Helper Functions
// =============================================================================

const char* authModeToString(wifi_auth_mode_t authmode) {
  switch (authmode) {
    case WIFI_AUTH_OPEN:
      return "OPEN";
    case WIFI_AUTH_WEP:
      return "WEP";
    case WIFI_AUTH_WPA_PSK:
      return "WPA_PSK";
    case WIFI_AUTH_WPA2_PSK:
      return "WPA2_PSK";
    case WIFI_AUTH_WPA_WPA2_PSK:
      return "WPA_WPA2_PSK";
    case WIFI_AUTH_WPA2_ENTERPRISE:
      return "WPA2_ENTERPRISE";
    case WIFI_AUTH_WPA3_PSK:
      return "WPA3_PSK";
    case WIFI_AUTH_WPA2_WPA3_PSK:
      return "WPA2_WPA3_PSK";
    case WIFI_AUTH_WAPI_PSK:
      return "WAPI_PSK";
    case WIFI_AUTH_OWE:
      return "OWE";
    case WIFI_AUTH_WPA3_ENT_192:
      return "WPA3_ENT_192";
    case WIFI_AUTH_WPA3_EXT_PSK:
    case WIFI_AUTH_WPA3_EXT_PSK_MIXED_MODE:
      return "WPA3_PSK";
    case WIFI_AUTH_DPP:
      return "DPP";
    case WIFI_AUTH_WPA3_ENTERPRISE:
      return "WPA3_ENTERPRISE";
    case WIFI_AUTH_WPA2_WPA3_ENTERPRISE:
      return "WPA2_WPA3_ENTERPRISE";
    case WIFI_AUTH_WPA_ENTERPRISE:
      return "WPA_ENTERPRISE";
    default:
      return "UNKNOWN";
  }
}

String escapeJsonString(const String& input) {
  String output = "";
  output.reserve(input.length() + 8);
  for (unsigned int i = 0; i < input.length(); i++) {
    char c = input.charAt(i);
    if (c == '"') {
      output += "\\\"";
    } else if (c == '\\') {
      output += "\\\\";
    } else if (c == '\b') {
      output += "\\b";
    } else if (c == '\f') {
      output += "\\f";
    } else if (c == '\n') {
      output += "\\n";
    } else if (c == '\r') {
      output += "\\r";
    } else if (c == '\t') {
      output += "\\t";
    } else if ((uint8_t)c >= 32) {
      // Preserve all printable ASCII and all valid UTF-8 multibyte characters (128-255)
      output += c;
    }
  }
  return output;
}

bool connectToTransportNetwork() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  Serial.printf("[WIFI] Associating with transport network '%s'...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WIFI] Associated! IP: %s | Gateway: %s | Signal: %d dBm\n",
                  WiFi.localIP().toString().c_str(),
                  WiFi.gatewayIP().toString().c_str(),
                  WiFi.RSSI());
    return true;
  } else {
    Serial.printf("[WIFI FAILED] Status code: %d\n", WiFi.status());
    return false;
  }
}

// =============================================================================
// Arduino Setup & Loop
// =============================================================================

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println();
  Serial.println("==================================================");
  Serial.println("[RF-THREAT-DETECTION] ESP32-U Live Ingest Client");
  Serial.println("Hardware: ESP32-U Dev Board w/ 3dBi Antenna");
  Serial.println("Stage: Production Hardware Ingest Client");
  Serial.printf("Config: Pod ID='%s' | Backend=http://%s:%d/api/ingest\n",
                POD_ID, BACKEND_HOST, BACKEND_PORT);
  Serial.println("==================================================");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(200);

  uint8_t baseMac[6];
  esp_err_t ret = esp_efuse_mac_get_default(baseMac);
  String staMac = WiFi.macAddress();
  if (ret == ESP_OK) {
    Serial.printf("[HW_IDENTITY] EFUSE Base MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  baseMac[0], baseMac[1], baseMac[2], baseMac[3], baseMac[4], baseMac[5]);
  }
  Serial.printf("[HW_IDENTITY] WiFi STA MAC:   %s\n", staMac.c_str());
  Serial.printf("[HW_IDENTITY] Active POD_ID:  %s\n", POD_ID);
}

void loop() {
  scanCycle++;
  Serial.println("--------------------------------------------------");
  Serial.printf("[CYCLE #%lu] Starting passive RF scan... (Heap: %u bytes)\n",
                scanCycle, ESP.getFreeHeap());

  // 1. Perform passive Wi-Fi scan across all 2.4 GHz channels (including hidden)
  unsigned long scanStartMs = millis();
  int16_t n = WiFi.scanNetworks(/*async=*/false, /*show_hidden=*/true);
  unsigned long scanDurationMs = millis() - scanStartMs;

  if (n < 0) {
    Serial.printf("[SCAN ERROR] Scan failed with code %d. Resetting Wi-Fi stack...\n", n);
    WiFi.disconnect();
    delay(CYCLE_DELAY_MS);
    return;
  }

  Serial.printf("[SCAN SUCCESS] Found %d AP(s) in %lu ms\n", n, scanDurationMs);

  // 2. Format JSON according to docs/data_contracts.md and observation.py
  // Schema: {"pod_id": "...", "timestamp_ms": ..., "observations": [...]}
  String jsonPayload = "";
  jsonPayload.reserve(n * 120 + 128);

  jsonPayload += "{\"pod_id\":\"";
  jsonPayload += POD_ID;
  jsonPayload += "\",\"timestamp_ms\":";
  jsonPayload += String(millis());
  jsonPayload += ",\"observations\":[";

  for (int16_t i = 0; i < n; i++) {
    if (i > 0) {
      jsonPayload += ",";
    }

    String ssid = WiFi.SSID(i);
    String bssid = WiFi.BSSIDstr(i);
    int32_t rssi = WiFi.RSSI(i);
    int32_t channel = WiFi.channel(i);
    wifi_auth_mode_t auth = WiFi.encryptionType(i);
    const char* authStr = authModeToString(auth);

    jsonPayload += "{\"bssid\":\"";
    jsonPayload += bssid;
    jsonPayload += "\",\"ssid\":\"";
    jsonPayload += escapeJsonString(ssid);
    jsonPayload += "\",\"rssi\":";
    jsonPayload += String(rssi);
    jsonPayload += ",\"channel\":";
    jsonPayload += String(channel);
    jsonPayload += ",\"authmode\":\"";
    jsonPayload += authStr;
    jsonPayload += "\"}";

    if (i < 3 || i == n - 1) {
      Serial.printf("  [%d/%d] %s (%s) %d dBm ch%d [%s]\n",
                    i + 1, n, bssid.c_str(), ssid.c_str(), rssi, channel, authStr);
    } else if (i == 3) {
      Serial.println("  ... [additional APs omitted from serial summary] ...");
    }
  }
  jsonPayload += "]}";

  // Free scan memory before network transmission
  WiFi.scanDelete();

  // 3. Connect to transport network
  bool connected = connectToTransportNetwork();
  if (!connected) {
    Serial.println("[HTTP ABORT] Skipping POST: Could not associate with transport AP.");
    delay(CYCLE_DELAY_MS);
    return;
  }

  // 4. Send HTTP POST to /api/ingest
  HTTPClient http;
  String targetUrl = String("http://") + BACKEND_HOST + ":" + BACKEND_PORT + "/api/ingest";
  Serial.printf("[HTTP POST] Sending %d observations (%u bytes) to %s\n",
                n, jsonPayload.length(), targetUrl.c_str());

  http.begin(targetUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  unsigned long postStartMs = millis();
  int httpCode = http.POST(jsonPayload);
  unsigned long postDurationMs = millis() - postStartMs;

  if (httpCode == 200) {
    String responseBody = http.getString();
    if (responseBody.indexOf("\"status\":\"accepted\"") >= 0) {
      Serial.printf("[INGEST SUCCESS] Ingested %d APs in %lu ms | Response: %s\n",
                    n, postDurationMs, responseBody.c_str());
      Serial.printf("[HW_IDENTITY] Pod: %s | WiFi MAC: %s\n", POD_ID, WiFi.macAddress().c_str());
    } else {
      Serial.printf("[INGEST UNEXPECTED] Code 200 but unexpected payload: %s\n",
                    responseBody.c_str());
    }
  } else if (httpCode > 0) {
    String responseBody = http.getString();
    Serial.printf("[INGEST REJECTED] HTTP %d (in %lu ms) | Error: %s\n",
                  httpCode, postDurationMs, responseBody.c_str());
  } else {
    Serial.printf("[HTTP ERROR] Transport failed: %s (code %d in %lu ms)\n",
                  http.errorToString(httpCode).c_str(), httpCode, postDurationMs);
  }

  http.end();

  // Disconnect from transport so next cycle can perform a clean channel-hopping scan
  WiFi.disconnect();

  Serial.printf("[CYCLE #%lu COMPLETE] Heap free: %u bytes. Resting for %lu ms...\n\n",
                scanCycle, ESP.getFreeHeap(), CYCLE_DELAY_MS);
  delay(CYCLE_DELAY_MS);
}
