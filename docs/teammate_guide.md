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

## 2. Meta Quest / VR Development (Developer 2)

### Goal
Connect to the backend WebSocket stream and render the 3D spatial threat volume around the estimated physical transmitter location.

### WebSocket Connection
- **Endpoint**: `ws://<backend-laptop-ip>:8000/ws/threats`
- Emits continuous threat state JSON packets (10 Hz).

### Coordinate Transformation
The backend defines a 2D metric coordinate system:
- Pod A: $(0.0, 0.0)$
- Pod B: $(4.0, 0.0)$
- Pod C: $(2.0, 3.5)$

In Unity / Unreal / WebXR:
- Backend $X \rightarrow$ Room $X$ (meters)
- Backend $Y \rightarrow$ Room $Z$ (meters forward)
- Fixed vertical offset $Y \approx 1.0\text{ m}$ (table/antenna height).

### Visual Elements to Render:
1. **Sensor Pod Markers**: 3 subtle indicators in physical space at $(0, 0)$, $(4, 0)$, and $(2, 3.5)$.
2. **Threat Volume**:
   - Render a volumetric sphere, translucent particle cloud, or pulsing shader at `threat.estimated_position_2d`.
   - **Radius**: Scale diameter directly with `threat.uncertainty_radius_m`. When uncertainty is high, cloud expands and diffuses. When confidence is high, cloud tightens.
   - **Color / Pulse**: Modulate color from orange to intense red based on `threat.risk_score` (0–100).
   - **HUD / Tooltip**: Show `threat.ssid`, `threat.bssid`, and `threat.evidence_flags` (e.g. `UNKNOWN_BSSID`, `SECURITY_MISMATCH`).
