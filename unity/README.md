# Meta Quest Pro Spatial Visualization Client

This folder contains the standalone Unity project for the **Meta Quest Pro** spatial RF threat visualization client.

---

## Architecture Overview

```text
Backend WebSocket (/ws/threats)
            ↓
  ThreatWebSocketClient.cs
            ↓ JSON Deserialization
    ThreatStateModels.cs
            ↓ Dispatched on Main Thread
ThreatVisualizationManager.cs
    ├── RoomCoordinateTransformer.cs  (Maps 2D backend plane -> 3D Quest Room)
    ├── ThreatVolumeController.cs     (Volumetric 3D threat cloud & Billboard HUD)
    ├── SensorNodeVisualizer.cs       (Physical Pod A, B, C markers & boundary)
    └── QuestPassthroughManager.cs    (Passthrough camera clear flags & alpha blending)
```

---

## Recommended Development Stack

- **Engine**: Unity 2022.3 LTS (recommended `2022.3.20f1`+) or Unity 6.
- **Unity Hub Modules Required for Device Build**:
  - `Android Build Support`
  - `Android SDK & NDK Tools`
  - `OpenJDK`
- **XR Plugin**: OpenXR (`com.unity.xr.openxr`) with Meta Quest Feature Group enabled.
- **Target Platform**: Android (ARM64, ASTC texture compression).
- **Target Device**: Meta Quest Pro (and Meta Quest 3/2 compatible).

---

## Project Structure

```text
unity/
├── Assets/
│   ├── Scenes/
│   │   └── MainThreatVisualization.unity   # Ready-to-use demo scene
│   └── Scripts/
│       ├── Models/
│       │   └── ThreatStateModels.cs         # C# data models matching /ws/threats contract
│       ├── Spatial/
│       │   ├── RoomCoordinateTransformer.cs # Isolated 2D -> 3D coordinate converter
│       │   └── QuestPassthroughManager.cs   # Passthrough camera setup (Color(0,0,0,0))
│       ├── Network/
│       │   └── ThreatWebSocketClient.cs     # Async WebSocket client with auto-reconnect
│       ├── Visualization/
│       │   ├── ThreatVisualizationManager.cs # Spawns, updates, and destroys threats
│       │   ├── ThreatVolumeController.cs    # Volumetric cloud scaling & billboard HUD
│       │   └── SensorNodeVisualizer.cs      # Renders Pod A, B, C markers
│       ├── Dev/
│       │   └── QuestDevTestRunner.cs        # On-screen test HUD & offline mock simulator
│       └── Editor/
│           └── SceneSetupHelper.cs          # Menu item to auto-configure demo scene
├── Packages/
│   └── manifest.json                        # Unity package dependencies
└── ProjectSettings/
    └── ProjectVersion.txt                   # Editor version lock (2022.3.20f1)
```

---

## Quick Start in Unity Editor

1. Open **Unity Hub**, click **Add project from disk**, and select the `unity/` folder.
2. Select Unity version `2022.3.20f1` (or any installed 2022.3 LTS release).
3. In the Unity top menu bar, select:
   **`RF Threat Detection` -> `Setup Demo Scene`**
   *(Or open `Assets/Scenes/MainThreatVisualization.unity` directly)*
4. Press **Play** in the Unity Editor:
   - The on-screen GUI will appear in the top-left corner.
   - **Mock Mode**: Toggle **Enable Mock** to simulate local moving threat frames directly in the Editor without needing Python or hardware.
   - **Live Backend**: Run the Python backend (`uvicorn backend.app.main:app`), and click **Connect**. It will connect to `ws://127.0.0.1:8000/ws/threats`.
   - **Passthrough Preview**: Press `P` to toggle between Passthrough mode (transparent camera) and VR Dark Void mode.

---

## Deploying to Meta Quest Pro

1. **Build Settings**:
   - Go to **File -> Build Settings**.
   - Select **Android** and click **Switch Platform**.
   - Set **Texture Compression** to `ASTC`.
   - Add `Assets/Scenes/MainThreatVisualization.unity` to **Scenes in Build**.
2. **XR Plug-in Management**:
   - Go to **Edit -> Project Settings -> XR Plug-in Management**.
   - Under the **Android** tab, check **OpenXR**.
   - Under OpenXR feature groups, enable **Meta Quest Support**.
3. **Backend Network Connection**:
   - Inspect the `[RFThreatSystem]` GameObject in the hierarchy.
   - In `ThreatWebSocketClient`, set `Server Uri` to your laptop's local LAN IP:
     `ws://192.168.X.X:8000/ws/threats`
   - Verify both laptop and Quest Pro are on the same local Wi-Fi.
4. **Deploy**:
   - Connect the Quest Pro via USB-C (ensure Developer Mode is enabled in Meta Quest mobile app).
   - Click **Build and Run**.
