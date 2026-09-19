# Teammate Guide: ESP32 Firmware & VR Development

**Target Hardware:**
- Sensor Nodes: 3x ESP32 (Pods A, B, C)
- Rogue AP: 1x ESP32 (SoftAP mode)
- Spatial Client: Meta Quest Headset

---

## 1. ESP32 Firmware Development (Developer 2)

### Goal
Implement lightweight firmware for the three sensor ESP32 pods to continuously scan nearby Wi-Fi APs and send observation batches to the laptop backend.

### What the ESP32 Needs to Transmit
The laptop backend expects JSON matching this contract:
```json
{
  "pod_id": "pod_a",
  "observations": [
    {
      "bssid": "DE:AD:BE:EF:00:01",
      "ssid": "HTN-Secure",
      "rssi": -55,
      "channel": 1,
      "authmode": "OPEN"
    }
  ]
}
```

### Initial Firmware Strategy: Standard AP Scan
Use standard Wi-Fi station scan:
- **Arduino ESP32**: `WiFi.scanNetworks(false, true)` (asynchronous or blocking).
- **ESP-IDF**: `esp_wifi_scan_start()` with `wifi_scan_config_t`.
- Do **NOT** implement promiscuous packet sniffing initially. Standard active/passive scanning yields standard SSID, BSSID, RSSI, channel, and authmode without raw 802.11 frame parsing.

### Hardware Questions to Verify on Real ESP32:
1. **Authmode representation**: Verify what enum values the scan API returns (`WIFI_AUTH_OPEN`, `WIFI_AUTH_WPA2_PSK`, etc.) and map them to human-readable strings.
2. **Scan rate**: Measure how long a full 2.4 GHz scan (channels 1-13) takes. (Typically 1.2 to 2.5 seconds per scan cycle).
3. **Transport**:
   - Simplest initial: Connect ESP32 to a local Wi-Fi router / hotspot sharing the network with the laptop, and send HTTP `POST http://<laptop-ip>:8000/api/ingest`.
   - Optional low-overhead: UDP broadcast/unicast packet on a dedicated port.

### Rogue AP Firmware (Pod #4)
- Run in `WIFI_MODE_AP` (SoftAP).
- Broadcast SSID: `HTN-Secure`
- Set security to open (`WIFI_AUTH_OPEN`) or mismatched WPA2 password.
- Set channel to `1` (mismatched from authorized channel `6`).
- Physical mobility: Power via USB power bank and carry across the room during the demo.

---

## 2. Meta Quest Pro / Unity VR Development (Developer 2)

### Project Location
A complete, isolated Unity project is set up at:
`unity/` (open this folder in Unity Hub / Unity 2022.3 LTS or Unity 6).

### Architecture & Scripts Overview
All C# scripts are located in `unity/Assets/Scripts/`:
1. **`Network/ThreatWebSocketClient.cs`**:
   - Manages connection to `ws://<laptop-ip>:8000/ws/threats`.
   - Uses .NET `ClientWebSocket` with background receive loop and main-thread event dispatching.
   - Dispatches `OnThreatStateReceived(ThreatStateData state)`.
   - Automatically reconnects if connection drops.
2. **`Spatial/RoomCoordinateTransformer.cs`**:
   - Isolates all 2D backend $\rightarrow$ 3D Quest spatial room transformations.
   - Maps $(X, Y)$ backend meters to $(X, Z)$ room space at calibrated height ($Y=1.0\text{m}$).
   - Supports runtime recalibration of room origin and yaw alignment.
3. **`Spatial/QuestPassthroughManager.cs`**:
   - Manages Passthrough rendering by clearing camera background to `Color(0,0,0,0)`.
   - Allows toggling Passthrough on/off in Editor with key `P` or runtime toggle.
4. **`Visualization/ThreatVisualizationManager.cs`**:
   - Core manager tracking active threat GameObjects by `threat_id`.
   - Spawns, smoothly moves, and removes threat volumes when they disappear from the stream.
5. **`Visualization/ThreatVolumeController.cs`**:
   - Attached to each threat volume.
   - Smoothly lerps spatial position towards target coordinates.
   - Scales volumetric sphere diameter to $2 \times \text{uncertainty\_radius\_m}$.
   - Shifts color from amber to critical red based on `risk_score` ($40$ to $100$).
   - Manages world-space billboard HUD showing SSID, BSSID, and evidence flags facing the VR camera.
6. **`Visualization/SensorNodeVisualizer.cs`**:
   - Renders 3D markers for Pods A, B, C and reference boundary lines outlining the monitored area.
7. **`Dev/QuestDevTestRunner.cs`**:
   - On-screen GUI overlay in Editor/VR showing connection status, active threat metrics, and manual connect/disconnect controls.
   - Includes local mock simulation fallback for testing in Unity Editor without running Python.
8. **`Editor/SceneSetupHelper.cs`**:
   - Adds top menu item `RF Threat Detection -> Setup Demo Scene` to configure everything in one click.

### How to Test in Unity Editor:
1. Open `unity/` in Unity Hub.
2. Open `Assets/Scenes/MainThreatVisualization.unity` (or click `RF Threat Detection -> Setup Demo Scene`).
3. Hit **Play**:
   - If the backend is running (`uvicorn backend.app.main:app`), click **Connect** in the on-screen overlay.
   - If offline, toggle **Enable Mock** in the on-screen HUD to see the volumetric threat cloud float and move along the simulated path in the Editor.
   - Press **P** to toggle passthrough mode / VR dark void mode.

### How to Deploy to Meta Quest Pro:
1. Install **Android Build Support**, **Android SDK & NDK Tools**, and **OpenJDK** via Unity Hub.
2. In Unity, switch build platform to **Android** (ASTC texture compression).
3. In **XR Plug-in Management**, enable **OpenXR** and enable the **Meta Quest Support** feature group under Android.
4. In `ThreatWebSocketClient`, set `Server Uri` to `ws://<laptop-local-ip>:8000/ws/threats`.
5. Connect Quest Pro via USB-C and select **Build and Run**.
