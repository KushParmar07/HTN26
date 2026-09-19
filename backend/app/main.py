"""FastAPI backend application exposing REST ingestion and WebSocket threat streaming."""

import asyncio
from contextlib import asynccontextmanager
import json
import time
from typing import Any, Dict, List, Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import DEFAULT_CONFIG
from backend.app.models.observation import PodObservationBatch
from backend.app.models.threat import ThreatStateResponse
from backend.app.pipeline import BackendPipeline

pipeline = BackendPipeline(config=DEFAULT_CONFIG)
connected_websockets: Set[WebSocket] = set()


async def broadcast_threat_state() -> None:
    """Broadcast current threat state to all connected WebSocket clients."""
    if not connected_websockets:
        return
    state = pipeline.generate_threat_state()
    data = state.model_dump_json()
    stale_sockets = set()
    for ws in connected_websockets:
        try:
            await ws.send_text(data)
        except Exception:
            stale_sockets.add(ws)
    for ws in stale_sockets:
        connected_websockets.discard(ws)


async def heartbeat_loop():
    """Background task providing periodic state refresh and WebSocket heartbeat."""
    interval = pipeline.config.websocket_heartbeat_interval_s
    while True:
        try:
            await asyncio.sleep(interval)
            await broadcast_threat_state()
        except asyncio.CancelledError:
            break
        except Exception as e:
            # Continue running ticker despite unexpected broadcast errors
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan managing background tasks."""
    ticker = asyncio.create_task(heartbeat_loop())
    yield
    ticker.cancel()
    try:
        await ticker
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="RF Threat Detection Backend",
    version="1.0.0",
    description="Distributed RF sensing and spatial threat detection for VR",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Production / Operational Endpoints
# =============================================================================

@app.get("/health", tags=["Operational"])
def get_health() -> Dict[str, Any]:
    """Health check returning backend status, active AP count, and connected VR headsets."""
    return {
        "status": "ok",
        "active_aps_count": len(pipeline.state_manager.get_all_aps()),
        "connected_vr_clients": len(connected_websockets),
        "configured_pods": [node.pod_id for node in pipeline.config.sensor_nodes],
    }


@app.post("/api/ingest", tags=["Ingestion"])
async def ingest_observations(batch: PodObservationBatch) -> Dict[str, Any]:
    """Ingest a batch of Wi-Fi AP observations from an ESP32 sensing pod or simulator."""
    pipeline.ingest(batch)
    # Broadcast updated threat state with zero latency
    await broadcast_threat_state()
    return {"status": "accepted", "pod_id": batch.pod_id, "count": len(batch.observations)}


@app.get("/api/threats", response_model=ThreatStateResponse, tags=["Threat State"])
def get_threats() -> ThreatStateResponse:
    """Retrieve an instantaneous snapshot of active threats in Meta Quest format."""
    return pipeline.generate_threat_state()


@app.get("/api/aps", tags=["Operational"])
def get_aps() -> List[Dict[str, Any]]:
    """Retrieve all monitored AP records and per-pod filtered RSSI history."""
    now_ms = int(time.time() * 1000)
    records = []
    for ap in pipeline.state_manager.get_all_aps():
        records.append(
            {
                "bssid": ap.bssid,
                "ssid": ap.ssid,
                "current_channel": ap.current_channel,
                "authmode": ap.authmode,
                "first_seen_ms": ap.first_seen_ms,
                "last_seen_ms": ap.last_seen_ms,
                "observation_count": ap.observation_count,
                "active_pods": ap.get_active_pods(now_ms=now_ms),
                "filtered_rssi": {
                    pod_id: ap.get_filtered_rssi(pod_id) for pod_id in ap.pod_filters
                },
                "smoothed_position_2d": (
                    {"x": ap.estimated_pos.x, "y": ap.estimated_pos.y}
                    if ap.estimated_pos
                    else None
                ),
                "uncertainty_radius_m": ap.uncertainty_radius_m,
            }
        )
    return records


@app.websocket("/ws/threats")
async def websocket_threats(websocket: WebSocket):
    """
    WebSocket endpoint streaming real-time threat state to Meta Quest VR clients.
    Clients receive an immediate state snapshot upon connection and live pushes thereafter.
    """
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        # Immediately push current state upon connect/reconnect
        initial_state = pipeline.generate_threat_state()
        await websocket.send_text(initial_state.model_dump_json())

        # Keep connection open; handle optional client pings/messages
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
    except Exception:
        connected_websockets.discard(websocket)


# =============================================================================
# Development & Testing Endpoints (Clearly Gated)
# =============================================================================

@app.post(
    "/api/reset",
    tags=["Development & Testing"],
    summary="[DEV/TEST ONLY] Reset all AP and threat state",
)
def reset_pipeline() -> Dict[str, Any]:
    """
    Reset all monitored APs and threat histories.
    Only active when enable_dev_endpoints is True.
    """
    if not pipeline.config.enable_dev_endpoints:
        raise HTTPException(status_code=403, detail="Development endpoints are disabled.")
    pipeline.reset()
    return {"status": "reset", "message": "All AP states and threat histories cleared"}
