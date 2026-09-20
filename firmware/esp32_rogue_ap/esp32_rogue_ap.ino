#include <Arduino.h>
#include <WiFi.h>
#include <esp_mac.h>

// =============================================================================
// Rogue AP Firmware for Controlled RF Threat Localization & Detection Testing
// Hardware Target: ESP32-WROOM (e.g., Freenove ESP32-WROOM)
// Note: Purely transmits controlled 802.11 beacons / frames for RF sensing.
//       No captive portal, credential harvesting, or exploitation payloads.
// =============================================================================

// Default AP configuration
String apSSID = "CorpNet-Secure";
String apPassword = ""; // Empty string = OPEN network
int apChannel = 6;
bool apRunning = false;

// Periodic status report timer
unsigned long lastStatusPrintMs = 0;
const unsigned long STATUS_INTERVAL_MS = 10000;

void printStatus() {
  Serial.println("\n========== ROGUE AP STATUS ==========");
  Serial.print("State:        ");
  Serial.println(apRunning ? "RUNNING (ACTIVE TRANSMITTING)" : "STOPPED (IDLE)");
  Serial.print("SSID:         ");
  Serial.println(apSSID);
  Serial.print("Channel:      ");
  Serial.println(apChannel);
  Serial.print("Security:     ");
  Serial.println(apPassword.length() == 0 ? "OPEN" : "WPA2_PSK");
  if (apRunning) {
    Serial.print("AP IP:        ");
    Serial.println(WiFi.softAPIP());
    Serial.print("AP MAC:       ");
    Serial.println(WiFi.softAPmacAddress());
    Serial.print("Connected Stas: ");
    Serial.println(WiFi.softAPgetStationNum());
  }
  Serial.println("=====================================\n");
}

void printHelp() {
  Serial.println("\n--- Rogue AP Interactive CLI Commands ---");
  Serial.println("  SET SSID <name>     : Set AP SSID (e.g. SET SSID CorpNet-Secure)");
  Serial.println("  SET CHANNEL <1-13>  : Set AP Channel (e.g. SET CHANNEL 6)");
  Serial.println("  SET PASSWORD <pass> : Set WPA2 password, or empty/none for OPEN (min 8 chars)");
  Serial.println("  START               : Launch SoftAP with current configuration");
  Serial.println("  STOP                : Shut down SoftAP");
  Serial.println("  STATUS              : Print current configuration and state");
  Serial.println("  HELP                : Show this command menu");
  Serial.println("-----------------------------------------\n");
}

void startAP() {
  if (apRunning) {
    WiFi.softAPdisconnect(true);
    delay(100);
  }

  WiFi.mode(WIFI_AP);
  const char* pass = (apPassword.length() >= 8) ? apPassword.c_str() : nullptr;
  bool ok = WiFi.softAP(apSSID.c_str(), pass, apChannel, 0, 4);

  if (ok) {
    apRunning = true;
    Serial.println("[+] SoftAP started successfully!");
    printStatus();
  } else {
    apRunning = false;
    Serial.println("[-] Failed to start SoftAP.");
  }
}

void stopAP() {
  if (apRunning) {
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_OFF);
    apRunning = false;
    Serial.println("[*] SoftAP stopped. RF transmitter disabled.");
  } else {
    Serial.println("[*] SoftAP is already stopped.");
  }
}

void processCliCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd.equalsIgnoreCase("HELP") || cmd.equalsIgnoreCase("?")) {
    printHelp();
  } else if (cmd.equalsIgnoreCase("STATUS")) {
    printStatus();
  } else if (cmd.equalsIgnoreCase("START")) {
    startAP();
  } else if (cmd.equalsIgnoreCase("STOP")) {
    stopAP();
  } else if (cmd.startsWith("SET SSID ") || cmd.startsWith("set ssid ")) {
    String newSsid = cmd.substring(9);
    newSsid.trim();
    if (newSsid.length() > 0 && newSsid.length() <= 32) {
      apSSID = newSsid;
      Serial.printf("[*] SSID updated to: '%s'\n", apSSID.c_str());
      if (apRunning) {
        Serial.println("[*] Restarting AP with new SSID...");
        startAP();
      }
    } else {
      Serial.println("[-] Error: SSID length must be between 1 and 32 characters.");
    }
  } else if (cmd.startsWith("SET CHANNEL ") || cmd.startsWith("set channel ")) {
    String chStr = cmd.substring(12);
    chStr.trim();
    int ch = chStr.toInt();
    if (ch >= 1 && ch <= 13) {
      apChannel = ch;
      Serial.printf("[*] Channel updated to: %d\n", apChannel);
      if (apRunning) {
        Serial.println("[*] Restarting AP on new channel...");
        startAP();
      }
    } else {
      Serial.println("[-] Error: Channel must be between 1 and 13.");
    }
  } else if (cmd.startsWith("SET PASSWORD ") || cmd.startsWith("set password ")) {
    String pw = cmd.substring(13);
    pw.trim();
    if (pw.equalsIgnoreCase("none") || pw.equalsIgnoreCase("open") || pw.length() == 0) {
      apPassword = "";
      Serial.println("[*] Password removed (Network is now OPEN).");
    } else if (pw.length() >= 8 && pw.length() <= 64) {
      apPassword = pw;
      Serial.printf("[*] Password set (%d chars, WPA2_PSK).\n", apPassword.length());
    } else {
      Serial.println("[-] Error: WPA2 password must be at least 8 characters, or 'none' for OPEN.");
      return;
    }
    if (apRunning) {
      Serial.println("[*] Restarting AP with new security profile...");
      startAP();
    }
  } else {
    Serial.printf("[-] Unrecognized command: '%s'. Type HELP for available commands.\n", cmd.c_str());
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n================================================");
  Serial.println("   ESP32 ROGUE AP TEST TRANSMITTER FIRMWARE    ");
  Serial.println("================================================");

  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
  Serial.printf("[*] Hardware SoftAP MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

  printHelp();
  // Start AP automatically on boot with defaults
  startAP();
}

void loop() {
  // Read Serial CLI commands
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    processCliCommand(line);
  }

  // Periodic heartbeat / status
  unsigned long now = millis();
  if (apRunning && (now - lastStatusPrintMs >= STATUS_INTERVAL_MS)) {
    lastStatusPrintMs = now;
    Serial.printf("[Heartbeat] AP '%s' active on ch %d | IP %s | Stas: %d\n",
                  apSSID.c_str(), apChannel,
                  WiFi.softAPIP().toString().c_str(),
                  WiFi.softAPgetStationNum());
  }

  delay(20);
}
