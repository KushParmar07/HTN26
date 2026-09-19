# Distributed RF Threat Detection & Spatial VR System

Distributed RF sensing and spatial localization system that makes wireless infrastructure threats (e.g. rogue APs / evil twins) physically visible in 3D VR space.

---

## Architecture Overview
- **RF Sensing**: Distributed ESP32 nodes ("Pods A, B, C") scanning 2.4 GHz spectrum.
- **Backend Pipeline**: Decoupled state management (`APStateManager`), temporal signal filtering (`CompositeRssiFilter`), explainable detection rules (`DeterministicDetector`), and 2D nonlinear multilateration (`MultilaterationSolver2D`).
- **Transport Layer**: FastAPI HTTP ingestion and WebSocket streaming engine with automated background heartbeat and state synchronization.
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

### 2. Running Automated Tests (28 tests)
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection pytest backend/tests -v
```

### 3. Starting the Backend Server
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 4. Running the Live Hackathon Demo Runner
Demonstrates the 3-phase live lifecycle (`NORMAL` -> `ROGUE AP DETECTED` -> `SPATIAL TRACKING`):
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection python -m simulator.demo_runner --interval 1.0
```

### 5. Running the Continuous Sensor Simulator
Streams configurable scenarios (`normal`, `suspicious`, `appearance`):
```powershell
& "C:\Users\KushP\miniconda3\condabin\conda.bat" run -n rf-threat-detection python -m simulator.sensor_simulator --scenario suspicious --interval 1.0
```

---

## API & WebSocket Endpoints

### Operational Endpoints
- `GET /health` - Backend health, active AP count, and connected VR clients
- `POST /api/ingest` - Sensor observation telemetry ingestion from pods or simulator
- `GET /api/threats` - Current active threat state snapshot for Meta Quest
- `GET /api/aps` - All monitored AP state records and per-pod filtered RSSI
- `WS /ws/threats` - Real-time streaming WebSocket broadcasting threat state updates

### Development & Testing Endpoints
- `POST /api/reset` - [DEV/TEST ONLY] Resets all tracked APs and active threats (gated by `enable_dev_endpoints`)
