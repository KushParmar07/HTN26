"""Integration test validating that backend output strictly adheres to the Meta Quest Unity contract."""

from fastapi.testclient import TestClient
from backend.app.main import app, pipeline
from simulator.config import ScenarioType, SimulatorConfig
from simulator.sensor_simulator import SensorSimulator

client = TestClient(app)


def test_quest_contract_field_coverage():
    pipeline.reset()
    sim = SensorSimulator(config=SimulatorConfig(random_seed=42))

    # Ingest suspicious scenario
    batches = sim.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.0, step_index=0, simulate_drops=False)
    for b in batches:
        resp = client.post("/api/ingest", json=b.model_dump())
        assert resp.status_code == 200

    # Query threat state
    res = client.get("/api/threats")
    assert res.status_code == 200
    data = res.json()

    # Verify top-level contract fields expected by ThreatStateData
    assert "version" in data and isinstance(data["version"], str)
    assert "generated_at_ms" in data and isinstance(data["generated_at_ms"], int)
    assert "sensor_nodes" in data and isinstance(data["sensor_nodes"], list)
    assert "threats" in data and isinstance(data["threats"], list)
    assert "active_threats" in data and isinstance(data["active_threats"], list)

    # Verify sensor nodes schema expected by SensorNodeData
    assert len(data["sensor_nodes"]) == 3
    for node in data["sensor_nodes"]:
        assert "pod_id" in node and isinstance(node["pod_id"], str)
        assert "x" in node and isinstance(node["x"], (int, float))
        assert "y" in node and isinstance(node["y"], (int, float))

    # Verify threat item schema expected by ThreatItemData
    assert len(data["threats"]) >= 1
    threat = data["threats"][0]

    assert "threat_id" in threat and isinstance(threat["threat_id"], str)
    assert threat["threat_id"].startswith("threat_")
    assert "bssid" in threat and isinstance(threat["bssid"], str)
    assert "ssid" in threat and isinstance(threat["ssid"], str)
    assert "status" in threat and isinstance(threat["status"], str)
    assert "risk_score" in threat and isinstance(threat["risk_score"], (int, float))
    assert "evidence_flags" in threat and isinstance(threat["evidence_flags"], list)
    assert "channel" in threat and isinstance(threat["channel"], int)
    assert "authmode" in threat and isinstance(threat["authmode"], str)
    assert "first_seen_ms" in threat and isinstance(threat["first_seen_ms"], int)
    assert "last_seen_ms" in threat and isinstance(threat["last_seen_ms"], int)
    assert "observed_by_pods" in threat and isinstance(threat["observed_by_pods"], list)
    assert "uncertainty_radius_m" in threat and isinstance(threat["uncertainty_radius_m"], (int, float))

    # Verify 2D position schema expected by Position2DData
    assert "estimated_position_2d" in threat and isinstance(threat["estimated_position_2d"], dict)
    pos = threat["estimated_position_2d"]
    assert "x" in pos and isinstance(pos["x"], (int, float))
    assert "y" in pos and isinstance(pos["y"], (int, float))


def test_quest_websocket_streaming_contract():
    pipeline.reset()
    sim = SensorSimulator(config=SimulatorConfig(random_seed=42))

    with client.websocket_connect("/ws/threats") as ws:
        init_frame = ws.receive_json()
        assert init_frame["version"] == "1.0"
        assert "sensor_nodes" in init_frame
        assert "threats" in init_frame
        assert "active_threats" in init_frame

        # Send test batch
        batches = sim.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.0, step_index=0)
        for b in batches:
            client.post("/api/ingest", json=b.model_dump())
            event = ws.receive_json()
            assert event["version"] == "1.0"
            assert "threats" in event
            assert "active_threats" in event
