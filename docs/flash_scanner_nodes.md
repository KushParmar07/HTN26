# Flash the three scanner nodes using Arduino IDE

Use `firmware/esp32_scanner/esp32_scanner.ino`, not the rogue-AP sketch.
This machine has Arduino IDE's bundled CLI and Espressif `esp32:esp32` core 3.3.7.
For the classic ESP-32U module use **ESP32 Dev Module** (`esp32:esp32:esp32`),
after confirming the board/module identity. Do not select Arduino Nano ESP32.

1. Enable the laptop's 2.4 GHz Mobile Hotspot. Read its actual name/password in
   Windows Settings and confirm the laptop's hotspot-adapter IPv4 with `ipconfig`.
   Use that adapter's address, not the phone's address or the laptop's upstream Wi-Fi address.
2. Label boards A, B and C. Plug in only A with a USB **data** cable.
3. Open the scanner `.ino` in Arduino IDE. Select **ESP32 Dev Module** and the USB
   COM port which appears when this board is plugged in. Bluetooth COM ports are
   not scanner ports. If no USB port appears, try a known data cable and USB port;
   identify the bridge in Device Manager before choosing a driver.
4. Edit only the configuration constants at the top:

   ```cpp
   const char* WIFI_SSID     = "YOUR_LAPTOP_HOTSPOT_NAME";
   const char* WIFI_PASSWORD = "YOUR_LAPTOP_HOTSPOT_PASSWORD";
   const char* BACKEND_HOST  = "YOUR_LAPTOP_HOTSPOT_IPV4";
   const int   BACKEND_PORT  = 8000;
   const char* POD_ID        = "pod_a";
   ```

   These are the data-transport network credentials. The phone being scanned may
   broadcast a different SSID. Keep credentials local; do not commit them.
5. Click **Verify**. Stop on a compile error. Select upload speed **115200** for
   initial bring-up, then click **Upload**. Verify alone does not flash the board.
   If upload stays at `Connecting...`, hold BOOT until writing begins, then release.
6. Open **Tools > Serial Monitor**, set **115200 baud**, and press EN/reset if needed.
   Confirm `Active POD_ID: pod_a`, record its EFUSE MAC, and check `[SCAN SUCCESS]`.
7. With the backend running on `0.0.0.0:8000`, confirm `[INGEST SUCCESS]` with an
   accepted response. `[WIFI FAILED]` indicates transport association trouble;
   `[HTTP ERROR]` indicates address/reachability/backend/firewall trouble. Stop and
   resolve failures before proceeding.
8. Close Serial Monitor and unplug A. Plug in B, reselect its COM port, change
   **only** `POD_ID` to `pod_b`, Verify, Upload, and check serial identity/ingestion.
9. Repeat for C using `pod_c`. Record each board's MAC beside its label to avoid
   duplicate identities. All three boards use the same transport credentials/IP.
10. Power the boards from USB power banks/adapters, place them in the configured
    triangle, and confirm a shared target BSSID is observed by all three pods.

Wireless nodes need power, not a USB data connection to the laptop. A spatial
heatmap requires an estimated location: this backend requires at least three
active observing pods. One/two-pod observations are still ingested but have no
new position estimate. Blue means below the risk threshold, not verified safe.
