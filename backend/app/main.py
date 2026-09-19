"""FastAPI backend application exposing REST ingestion and WebSocket threat streaming."""

import time
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import DEFAULT_CONFIG, SystemConfig
from backend.app.detection.rules import DeterministicDetector
from backend.app.localization.multilateration import MultilaterationSolver2D
from backend.app.models.observation import PodObservationBatch
from backend.app.models.threat import (
    SensorNodeInfo,
    ThreatItem,
    ThreatStateResponse,
    ThreatStatus,
)
from backend.app.state.ap_state import APStateManager


class BackendPipeline:
    """Core backend pipeline coordinating state, detection, and localization."""

    def __init__(self, config: SystemConfig = DEFAULT_CONFIG):
        self.config = config
        self.state_manager = APStateManager(
            stale_ttl_ms=config.stale_ap_ttl_ms,
            median_window=config.median_window,
            ema_alpha=config.ema_alpha,
        )
        self.detector = DeterministicDetector(
            authorized=config.authorized_network,
            weights=config.detection_weights,
            suspicious_threshold=config.suspicious_threshold,
            sudden_appearance_threshold_ms=config.sudden_appearance_threshold_ms,
        )
        self.solver = MultilaterationSolver2D(
            sensor_nodes=config.sensor_nodes,
            reference_rssi=config.path_loss_reference_rssi,
            path_loss_exponent=config.path_loss_exponent,
        )
        self.connected_websockets: Set[WebSocket] = set()

    def ingest(self, batch: PodObservationBatch, received_at_ms: Optional[int] = None) -> None:
        now_ms = received_at_ms if received_at_ms is not None else int(time.time() * 1000)
        self.state_manager.ingest_batch(batch, received_at_ms=now_ms)

    def generate_threat_state(self, current_time_ms: Optional[int] = None) -> ThreatStateResponse:
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
        self.state_manager.prune_stale(now_ms=now_ms)

        threat_items: List[ThreatItem] = []
        all_aps = self.state_manager.get_all_aps()

        for ap in all_aps:
            status, risk_score, flags = self.detector.evaluate(ap, current_time_ms=now_ms)

            # Get filtered RSSI per pod
            pod_rssi_map: Dict[str, float] = {}
            active_pods = ap.get_active_pods(now_ms=now_ms, max_age_ms=10000)
            for pod_id in active_pods:
                f_rssi = ap.get_filtered_rssi(pod_id)
                if f_rssi is not None:
                    pod_rssi_map[pod_id] = f_rssi

            # Solve 2D localization if AP is active
            pos_2d, uncertainty = self.solver.solve(pod_rssi_map)

            # We report any AP marked as SUSPICIOUS_INFRASTRUCTURE or with positive risk
            if status == ThreatStatus.SUSPICIOUS_INFRASTRUCTURE or risk_score >= self.config.suspicious_threshold:
                threat_items.append(
                    ThreatItem(
                        bssid=ap.bssid,
                        ssid=ap.ssid,
                        status=status,
                        risk_score=risk_score,
                        evidence_flags=flags,
                        estimated_position_2d=pos_2d,
                        uncertainty_radius_m=uncertainty,
                        last_seen_ms=ap.last_seen_ms,
                        observed_by_pods=active_pods,
                    )
                )

        sensor_nodes_info = [
            SensorNodeInfo(pod_id=node.pod_id, x=node.x, y=node.y)
            for node in self.config.sensor_nodes
        ]

        return ThreatStateResponse(
            version="1.0",
            generated_at_ms=now_ms,
            sensor_nodes=sensor_nodes_info,
            threats=threat_items,
        )

    async def broadcast_threat_state(self) -> None:
        if not self.connected_websockets:
            return
        state = self.generate_threat_state()
        data = state.model_dump_json()
        stale_sockets = set()
        for ws in self.connected_websockets:
            try:
                await ws.send_text(data)
            except Exception:
                stale_sockets.add(ws)
        for ws in stale_sockets:
            self.connected_websockets.discard(ws)

    def reset(self) -> None:
        """Clear all active AP states."""
        self.state_manager.aps.clear()


pipeline = BackendPipeline()
app = FastAPI(
    title="RF Threat Detection Backend",
    version="1.0.0",
    description="Distributed RF sensing and spatial threat detection for VR",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "active_aps_count": len(pipeline.state_manager.get_all_aps()),
        "connected_vr_clients": len(pipeline.connected_websockets),
        "configured_pods": [node.pod_id for node in pipeline.config.sensor_nodes],
    }


@app.post("/api/ingest")
async def ingest_observations(batch: PodObservationBatch) -> Dict[str, Any]:
    pipeline.ingest(batch)
    # Broadcast new state to all connected WebSocket clients upon batch ingestion
    await pipeline.broadcast_threat_state()
    return {"status": "accepted", "pod_id": batch.pod_id, "count": len(batch.observations)}


@app.post("/api/reset")
def reset_pipeline() -> Dict[str, Any]:
    pipeline.reset()
    return {"status": "reset", "message": "All AP states and threat histories cleared"}


@app.get("/api/threats", response_model=ThreatStateResponse)
def get_threats() -> ThreatStateResponse:
    return pipeline.generate_threat_state()


@app.get("/api/aps")
def get_aps() -> List[Dict[str, Any]]:
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
            }
        )
    return records


@app.websocket("/ws/threats")
async def websocket_threats(websocket: WebSocket):
    await websocket.accept()
    pipeline.connected_websockets.add(websocket)
    try:
        # Immediately send current state on connect
        initial_state = pipeline.generate_threat_state()
        await websocket.send_text(initial_state.model_dump_json())

        # Keep socket open to receive any pings/messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pipeline.connected_websockets.discard(websocket)
    except Exception:
        pipeline.connected_websockets.discard(websocket)
