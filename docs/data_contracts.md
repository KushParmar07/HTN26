# RF Threat Detection: Data Contracts Specification

**Version:** 1.0  
**Status:** Approved for Stage 1 Implementation  

---

## 1. Sensor Ingestion Contract (ESP32 / Simulator → Backend)

### Transport
- **Stage 1 (Simulated)**: HTTP `POST /api/ingest` (Content-Type: `application/json`)
- **Stage 2+ (Physical ESP32)**: Configurable UDP listener or HTTP POST

### Payload Schema
```json
{
  "pod_id": "pod_a",
  "timestamp_ms": 1726729200000,
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

### Field Definitions & Semantics

| Field | Type | Unit / Constraints | Hardware Verification Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| `pod_id` | `string` | Unique pod name: `"pod_a"`, `"pod_b"`, `"pod_c"` | **Verified** (Hardcoded firmware config) | Identifier of sensing node. |
| `timestamp_ms` | `integer` (optional) | Milliseconds (epoch or uptime) | **Needs Verification** | Time observation was taken on the pod. If missing or unsynced, backend attaches arrival time. |
| `observations` | `list[object]` | Array of AP observations | **Verified** | List of all APs visible in the current scan batch. |
| `observations[].bssid` | `string` | Normalized format: `AA:BB:CC:DD:EE:FF` | **Verified** | MAC address of the observed transmitter. Case-insensitive in ingest, normalized by backend. |
| `observations[].ssid` | `string` | 0 to 32 characters (can be empty string for hidden) | **Verified** | Broadcasted network name. |
| `observations[].rssi` | `integer` | dBm (typically -95 to -20) | **Verified** | Received signal strength indicator. |
| `observations[].channel`| `integer` | 1–14 (2.4 GHz) | **Verified** | Primary Wi-Fi operating channel. |
| `observations[].authmode`| `string` | Standardized string (`OPEN`, `WEP`, `WPA_PSK`, `WPA2_PSK`, `WPA_WPA2_PSK`, `WPA2_ENTERPRISE`, `WPA3_PSK`, `UNKNOWN`) | **Needs Verification** | Authentication mode string mapped from ESP32 enum. |

---

## 2. Threat State Contract (Backend → VR / Meta Quest)

### Transport
- WebSocket: `ws://<backend-ip>:8000/ws/threats`
- REST Polling: `GET http://<backend-ip>:8000/api/threats`

### Payload Schema
```json
{
  "version": "1.0",
  "generated_at_ms": 1726729205120,
  "sensor_nodes": [
    {"pod_id": "pod_a", "x": 0.0, "y": 0.0},
    {"pod_id": "pod_b", "x": 4.0, "y": 0.0},
    {"pod_id": "pod_c", "x": 2.0, "y": 3.5}
  ],
  "threats": [
    {
      "threat_id": "threat_deadbeef0001",
      "bssid": "DE:AD:BE:EF:00:01",
      "ssid": "HTN-Secure",
      "status": "SUSPICIOUS_INFRASTRUCTURE",
      "risk_score": 100.0,
      "evidence_flags": [
        "UNKNOWN_BSSID",
        "SECURITY_MISMATCH",
        "SUDDEN_APPEARANCE",
        "UNEXPECTED_CHANNEL"
      ],
      "estimated_position_2d": {
        "x": 1.85,
        "y": 1.20
      },
      "uncertainty_radius_m": 0.55,
      "channel": 1,
      "authmode": "OPEN",
      "first_seen_ms": 1726729200000,
      "last_seen_ms": 1726729205000,
      "observed_by_pods": ["pod_a", "pod_b", "pod_c"]
    }
  ],
  "active_threats": [...]
}
```

### Field Definitions & Semantics

| Field | Type | Description |
| :--- | :--- | :--- |
| `version` | `string` | Protocol version (`"1.0"`). |
| `generated_at_ms` | `integer` | Backend Unix epoch timestamp in ms when state was computed. |
| `sensor_nodes` | `list[object]` | Known positions of the 3 physical ESP32 sensing pods. |
| `threats` | `list[object]` | List of currently active detected threats (`risk_score >= threshold`). |
| `active_threats` | `list[object]` | Alias for `threats` for VR clients expecting active_threats field. |
| `threats[].threat_id` | `string` | Unique stable identifier (e.g. `"threat_deadbeef0001"`) for binding VR GameObjects/particles. |
| `threats[].bssid` | `string` | Normalized BSSID of the suspicious AP. |
| `threats[].ssid` | `string` | SSID of the suspicious AP. |
| `threats[].status` | `string` | `"SUSPICIOUS_INFRASTRUCTURE"` or `"AUTHORIZED"` or `"MONITORED"`. |
| `threats[].risk_score` | `float` | Bounded risk score from `0.0` to `100.0`. |
| `threats[].evidence_flags` | `list[string]` | Human-readable explainability flags triggering the risk score. |
| `threats[].estimated_position_2d` | `object` or `null` | Smoothed 2D coordinates `{ "x": float, "y": float }` in meters. `null` if $<3$ pods have observed it. |
| `threats[].uncertainty_radius_m` | `float` or `null` | 1-sigma uncertainty radius in meters. Controls VR threat volume radius. |
| `threats[].channel` | `integer` or `null` | Current Wi-Fi channel (e.g. 1) for HUD inspection. |
| `threats[].authmode` | `string` or `null` | Current security mode (e.g. `"OPEN"`) for HUD inspection. |
| `threats[].first_seen_ms` | `integer` | Unix timestamp ms when AP was first observed. |
| `threats[].last_seen_ms` | `integer` | Unix timestamp ms when any pod last observed this BSSID. |
| `threats[].observed_by_pods` | `list[string]` | Pod IDs that have observed this transmitter in the active time window. |

---

## 3. Coordinate System Conventions

1. **Units**: Metric meters ($m$).
2. **2D Plane**: $(X, Y)$ where:
   - Pod A is reference origin $(0.0, 0.0)$.
   - Pod B is along the baseline $(4.0, 0.0)$.
   - Pod C encloses the area $(2.0, 3.5)$.
3. **VR Mapping**:
   - Backend $X \rightarrow$ VR Room $X$ (Right).
   - Backend $Y \rightarrow$ VR Room $Z$ (Forward / Depth).
   - VR Room $Y$ (Height / Vertical) $\approx 0.0\text{ m}$ (floor level) or calibrated antenna height ($1.0\text{ m}$).
