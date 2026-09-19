"""Integration tests exercising deterministic normal, suspicious, and attack appearance scenarios."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, pipeline
from simulator.config import ScenarioType, SimulatorConfig
from simulator.sensor_simulator import SensorSimulator

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_pipeline():
    """Reset pipeline state before each test."""
    pipeline.reset()
    yield
    pipeline.reset()


def test_normal_environment_zero_false_positives():
    """Verify normal scenario with only legitimate and ambient APs produces zero threats."""
    cfg = SimulatorConfig(random_seed=123, rssi_noise_std=1.0)
    sim = SensorSimulator(config=cfg)

    # Ingest 5 steps of normal data
    for step in range(5):
        batches = sim.generate_step(
            scenario=ScenarioType.NORMAL,
            progress=step / 5.0,
            step_index=step,
            add_noise=True,
            simulate_drops=False,
        )
        for batch in batches:
            resp = client.post("/api/ingest", json=batch.model_dump())
            assert resp.status_code == 200

    # Query threats
    res = client.get("/api/threats")
    assert res.status_code == 200
    data = res.json()

    # In normal environment, NO active threats should be triggered
    assert len(data["threats"]) == 0

    # But /api/aps should list all 4 monitored APs (1 legitimate + 3 background)
    aps_res = client.get("/api/aps")
    assert aps_res.status_code == 200
    aps = aps_res.json()
    assert len(aps) == 4
    bssids = {ap["bssid"] for ap in aps}
    assert "00:11:22:33:44:55" in bssids  # Legitimate AP


def test_suspicious_scenario_detection_and_localization():
    """Verify suspicious scenario triggers threat with correct evidence and 2D position."""
    cfg = SimulatorConfig(random_seed=42, rssi_noise_std=1.0)
    sim = SensorSimulator(config=cfg)

    # Step 0: Rogue near (0.5, 0.5)
    batches = sim.generate_step(
        scenario=ScenarioType.SUSPICIOUS,
        progress=0.0,
        step_index=0,
        add_noise=False,
        simulate_drops=False,
    )
    for batch in batches:
        resp = client.post("/api/ingest", json=batch.model_dump())
        assert resp.status_code == 200

    res = client.get("/api/threats")
    assert res.status_code == 200
    threats = res.json()["threats"]

    assert len(threats) == 1
    rogue = threats[0]
    assert rogue["bssid"] == "DE:AD:BE:EF:00:01"
    assert rogue["status"] == "SUSPICIOUS_INFRASTRUCTURE"
    assert rogue["risk_score"] >= 80.0
    assert "UNKNOWN_BSSID" in rogue["evidence_flags"]
    assert "SECURITY_MISMATCH" in rogue["evidence_flags"]
    assert "UNEXPECTED_CHANNEL" in rogue["evidence_flags"]
    assert rogue["estimated_position_2d"] is not None
    assert rogue["estimated_position_2d"]["x"] == pytest.approx(0.5, abs=0.25)
    assert rogue["estimated_position_2d"]["y"] == pytest.approx(0.5, abs=0.25)


def test_attack_appearance_transition():
    """Verify transition from clean environment to sudden threat appearance."""
    cfg = SimulatorConfig(random_seed=99)
    sim = SensorSimulator(config=cfg)

    # Steps 0..2: Normal environment
    for step in range(3):
        batches = sim.generate_step(
            scenario=ScenarioType.ATTACK_APPEARANCE,
            progress=step / 10.0,
            step_index=step,
            appearance_step=3,
        )
        for batch in batches:
            client.post("/api/ingest", json=batch.model_dump())

    # Verify no threats during steps 0..2
    threats_before = client.get("/api/threats").json()["threats"]
    assert len(threats_before) == 0

    # Step 3: Rogue AP suddenly appears
    batches_step3 = sim.generate_step(
        scenario=ScenarioType.ATTACK_APPEARANCE,
        progress=3 / 10.0,
        step_index=3,
        appearance_step=3,
    )
    for batch in batches_step3:
        client.post("/api/ingest", json=batch.model_dump())

    # Verify threat is immediately detected
    threats_after = client.get("/api/threats").json()["threats"]
    assert len(threats_after) == 1
    assert threats_after[0]["bssid"] == "DE:AD:BE:EF:00:01"
    assert "SUDDEN_APPEARANCE" in threats_after[0]["evidence_flags"]


def test_deterministic_reproducibility():
    """Verify running simulator with same seed generates identical observations."""
    sim1 = SensorSimulator(config=SimulatorConfig(random_seed=777))
    batches1 = sim1.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.2, step_index=2)

    sim2 = SensorSimulator(config=SimulatorConfig(random_seed=777))
    batches2 = sim2.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.2, step_index=2)

    assert len(batches1) == len(batches2)
    for b1, b2 in zip(batches1, batches2):
        assert b1.pod_id == b2.pod_id
        assert len(b1.observations) == len(b2.observations)
        for o1, o2 in zip(b1.observations, b2.observations):
            assert o1.bssid == o2.bssid
            assert o1.rssi == o2.rssi


def test_full_pipeline_websocket_live_stream():
    """Verify end-to-end WebSocket stream receives real-time updates as batches arrive."""
    cfg = SimulatorConfig(random_seed=42)
    sim = SensorSimulator(config=cfg)

    with client.websocket_connect("/ws/threats") as ws:
        # Initial connect message
        init_msg = ws.receive_json()
        assert init_msg["version"] == "1.0"
        assert len(init_msg["threats"]) == 0  # Starts clean

        # Ingest one suspicious batch from pod_a, pod_b, pod_c
        batches = sim.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.0, step_index=0)
        for batch in batches:
            client.post("/api/ingest", json=batch.model_dump())
            # Ingest triggers broadcast_threat_state() -> receives message over WS
            event = ws.receive_json()
            assert event["version"] == "1.0"

        # Check latest event from websocket
        latest_threats = event["threats"]
        assert len(latest_threats) == 1
        assert latest_threats[0]["bssid"] == "DE:AD:BE:EF:00:01"
        assert latest_threats[0]["status"] == "SUSPICIOUS_INFRASTRUCTURE"
