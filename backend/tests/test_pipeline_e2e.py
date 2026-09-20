"""End-to-end integration tests validating simulator -> pipeline -> threat state & tracking."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, pipeline
from simulator.config import DEFAULT_SIMULATOR_CONFIG
from simulator.sensor_simulator import SensorSimulator

client = TestClient(app)


def test_e2e_moving_rogue_tracking():
    # Reset pipeline state
    pipeline.state_manager.aps.clear()

    sim = SensorSimulator(config=DEFAULT_SIMULATOR_CONFIG)

    # Step 1: Rogue AP at initial position inside the compact triangle.
    batches_step0 = sim.generate_step(progress=0.0, add_noise=False, simulate_drops=False)
    for batch in batches_step0:
        resp = client.post("/api/ingest", json=batch.model_dump())
        assert resp.status_code == 200

    state_0 = client.get("/api/threats").json()
    assert len(state_0["threats"]) == 1
    threat_0 = state_0["threats"][0]

    assert threat_0["bssid"] == "DE:AD:BE:EF:00:01"
    assert threat_0["status"] == "SUSPICIOUS_INFRASTRUCTURE"
    assert "UNKNOWN_BSSID" in threat_0["evidence_flags"]
    assert "SECURITY_MISMATCH" in threat_0["evidence_flags"]

    pos_0 = threat_0["estimated_position_2d"]
    assert pos_0 is not None
    assert pos_0["x"] == pytest.approx(0.3, abs=0.2)
    assert pos_0["y"] == pytest.approx(0.3, abs=0.2)

    # Step 2: Move rogue AP across the physical triangle (progress = 0.5 -> end).
    # Send multiple batches to let composite filter track the movement
    for _ in range(6):
        batches_step1 = sim.generate_step(progress=0.5, add_noise=False, simulate_drops=False)
        for batch in batches_step1:
            resp = client.post("/api/ingest", json=batch.model_dump())
            assert resp.status_code == 200

    state_1 = client.get("/api/threats").json()
    assert len(state_1["threats"]) == 1
    threat_1 = state_1["threats"][0]
    pos_1 = threat_1["estimated_position_2d"]

    assert pos_1 is not None
    assert pos_1["x"] > 1.1
    assert pos_1["y"] > 0.35


def test_e2e_websocket_threat_stream():
    # Test WebSocket connection with TestClient
    with client.websocket_connect("/ws/threats") as websocket:
        data = websocket.receive_json()
        assert data["version"] == "1.0"
        assert "sensor_nodes" in data
        assert len(data["sensor_nodes"]) == 3
        assert "threats" in data
