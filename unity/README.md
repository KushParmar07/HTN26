# Meta Quest Pro Spatial Visualization Client (Unity 6.3 LTS)

This folder contains the standalone Unity project for the **Meta Quest Pro** spatial RF threat visualization client, targeting **Unity 6.3 LTS** (`6000.6.2f1`).

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

## Target Development Stack

- **Engine**: Unity 6.3 LTS (Editor `6000.6.2f1`).
- **XR Packages**:
  - `com.unity.feature.vr` (1.0.1)
  - `com.unity.xr.openxr` (1.18.0)
  - `com.unity.xr.management` (4.7.0)
  - `com.unity.ugui` (2.6.0 with built-in TextMeshPro support)
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
│           ├── SceneSetupHelper.cs          # Menu item to auto-configure demo scene
│           └── PlayModeVerification.cs      # Automated batchmode verification test
├── Packages/
│   └── manifest.json                        # Unity 6 package dependencies
└── ProjectSettings/
    └── ProjectVersion.txt                   # Editor version lock (6000.6.2f1)
```

---

## Quick Start in Unity Editor

1. Open **Unity Hub**, click **Add project from disk**, and select the `unity/` folder.
2. Select Unity version **`6000.6.2f1`** (Unity 6.3 LTS).
3. Open `Assets/Scenes/MainThreatVisualization.unity` (or click `RF Threat Detection -> Setup Demo Scene`).
4. Press **Play** in the Unity Editor:
   - The on-screen GUI will appear in the top-left corner.
   - **Mock Mode**: Toggle **Enable Mock** to simulate local moving threat frames directly in the Editor without needing Python or hardware.
   - **Live Backend**: Run the Python backend (`uvicorn backend.app.main:app`), and click **Connect**. It connects to `ws://127.0.0.1:8000/ws/threats`.
   - **Passthrough Preview**: Press `P` to toggle between Passthrough mode (transparent camera) and VR Dark Void mode.

---

## Automated Verification via Command Line

You can run the full end-to-end verification test in batchmode:
```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.6.2f1\Editor\Unity.exe" -batchmode -nographics -projectPath "C:\Projects\Hackathon\HTN26\unity" -executeMethod RFThreatDetection.Editor.PlayModeVerification.RunVerification -logFile "unity_verification.log"
```
This automatically verifies:
- Scene creation and component wiring
- Camera passthrough clear flags
- Room coordinate 2D -> 3D transformation
- Sensor pod marker instantiation (Pods A, B, C)
- Volumetric moving threat rendering, uncertainty scaling ($2 \times r$), and billboard HUD updates
- Entering and exiting live Unity 6.3 Play Mode

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
   - In `ThreatWebSocketClient`, set `Server Uri` to your laptop's local LAN IP:
     `ws://192.168.X.X:8000/ws/threats`
   - Verify both laptop and Quest Pro are on the same local Wi-Fi.
4. **Deploy**:
   - Connect the Quest Pro via USB-C (ensure Developer Mode is enabled in Meta Quest mobile app).
   - Click **Build and Run**.
