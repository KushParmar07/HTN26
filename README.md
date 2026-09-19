# Distributed RF Threat Detection & Spatial VR System

Distributed RF sensing and spatial localization system that makes wireless infrastructure threats (e.g. rogue APs / evil twins) physically visible in 3D VR space.

---

## Architecture Overview
- **RF Sensing**: Distributed ESP32 nodes ("Pods A, B, C") scanning 2.4 GHz spectrum.
- **Backend**: FastAPI pipeline aggregating observations, filtering RSSI, evaluating deterministic security rules, and solving 2D transmitter position with uncertainty.
- **Spatial Visualization**: Meta Quest VR client streaming threat state over WebSocket and rendering volumetric threat clouds in physical room coordinates.

---

## Environment & Prerequisites
- **OS**: Windows (PowerShell)
- **Conda Environment**: `rf-threat-detection` (Python 3.14)
- **Location**: `C:\Users\KushP\miniconda3\envs\rf-threat-detection`

---

## Running Commands

### 1. Activating Conda Environment
```powershell
conda activate rf-threat-detection
```
Or run directly via Conda batch wrapper:
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection <command>
```

### 2. Running Automated Tests
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection pytest backend/tests -v
```

### 3. Starting the Backend Server
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Running the Sensor Simulator
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection python -m simulator.sensor_simulator
```

---

## API Endpoints
- `GET /health` - Backend health and pod status
- `POST /api/ingest` - Sensor observation telemetry ingestion
- `GET /api/threats` - Current active threat state snapshot
- `GET /api/aps` - All monitored AP state records
- `WS /ws/threats` - Real-time streaming threat state for VR / Meta Quest
