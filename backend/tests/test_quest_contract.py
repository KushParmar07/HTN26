import json
from fastapi.testclient import TestClient
from backend.app.main import app, pipeline
from backend.app.models.observation import PodObservationBatch, SingleObservation
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


# =============================================================================
# VR Integration & WebSocket Contract Verification
# =============================================================================

def test_quest_contract_zero_one_two_three_pod_states():
    """
    Verify the WebSocket payload representation across 0, 1, 2, and 3 pod states:
    - 0 pods: threats empty, sensor_nodes present
    - 1 pod: threat detected, estimated_position_2d is null, uncertainty_radius_m is null
    - 2 pods: threat detected, observed_by_pods has 2 pods, estimated_position_2d is null
    - 3 pods: threat detected, observed_by_pods has 3 pods, estimated_position_2d has valid x & y
    """
    pipeline.reset()

    with client.websocket_connect("/ws/threats") as ws:
        # 0 pods
        frame0 = ws.receive_json()
        assert frame0["threats"] == []
        assert frame0["active_threats"] == []
        assert len(frame0["sensor_nodes"]) == 3

        # 1 pod active
        client.post(
            "/api/ingest",
            json={
                "pod_id": "pod_a",
                "observations": [
                    {
                        "bssid": "DE:AD:BE:EF:00:01",
                        "ssid": "HTN-Secure",
                        "rssi": -50,
                        "channel": 1,
                        "authmode": "OPEN",
                    }
                ],
            },
        )
        frame1 = ws.receive_json()
        assert len(frame1["threats"]) == 1
        t1 = frame1["threats"][0]
        assert t1["bssid"] == "DE:AD:BE:EF:00:01"
        assert t1["ssid"] == "HTN-Secure"
        assert t1["status"] == "SUSPICIOUS_INFRASTRUCTURE"
        assert t1["observed_by_pods"] == ["pod_a"]
        assert t1["estimated_position_2d"] is None
        assert t1["uncertainty_radius_m"] is None

        # 2 pods active
        client.post(
            "/api/ingest",
            json={
                "pod_id": "pod_b",
                "observations": [
                    {
                        "bssid": "DE:AD:BE:EF:00:01",
                        "ssid": "HTN-Secure",
                        "rssi": -58,
                        "channel": 1,
                        "authmode": "OPEN",
                    }
                ],
            },
        )
        frame2 = ws.receive_json()
        assert len(frame2["threats"]) == 1
        t2 = frame2["threats"][0]
        assert sorted(t2["observed_by_pods"]) == ["pod_a", "pod_b"]
        assert t2["estimated_position_2d"] is None
        assert t2["uncertainty_radius_m"] is None

        # 3 pods active -> Multilateration calculates 2D position!
        client.post(
            "/api/ingest",
            json={
                "pod_id": "pod_c",
                "observations": [
                    {
                        "bssid": "DE:AD:BE:EF:00:01",
                        "ssid": "HTN-Secure",
                        "rssi": -54,
                        "channel": 1,
                        "authmode": "OPEN",
                    }
                ],
            },
        )
        frame3 = ws.receive_json()
        assert len(frame3["threats"]) == 1
        t3 = frame3["threats"][0]
        assert sorted(t3["observed_by_pods"]) == ["pod_a", "pod_b", "pod_c"]
        assert t3["estimated_position_2d"] is not None
        assert "x" in t3["estimated_position_2d"]
        assert "y" in t3["estimated_position_2d"]
        assert isinstance(t3["estimated_position_2d"]["x"], (int, float))
        assert isinstance(t3["estimated_position_2d"]["y"], (int, float))
        assert t3["uncertainty_radius_m"] is not None
        assert t3["uncertainty_radius_m"] >= 0.3


def test_quest_contract_strict_json_no_nan_or_infinity():
    """
    Verify that raw text received over /ws/threats is strictly standard JSON compliant
    and never outputs NaN, -NaN, Infinity, or -Infinity under any circumstance.
    """
    pipeline.reset()

    with client.websocket_connect("/ws/threats") as ws:
        # Initial connect frame
        initial_text = ws.receive_text()
        assert "NaN" not in initial_text
        assert "Infinity" not in initial_text
        json.loads(initial_text)

        # Ingest extreme inputs
        client.post(
            "/api/ingest",
            json={
                "pod_id": "pod_a",
                "observations": [
                    {
                        "bssid": "DE:AD:BE:EF:00:01",
                        "ssid": "HTN-Secure",
                        "rssi": -110,
                        "channel": 1,
                        "authmode": "OPEN",
                    }
                ],
            },
        )
        update_text = ws.receive_text()
        assert "NaN" not in update_text
        assert "Infinity" not in update_text
        assert "null" in update_text
        assert "estimated_position_2d" in update_text

        # Test standard json.loads parses cleanly
        parsed = json.loads(update_text)
        assert parsed["version"] == "1.0"
        assert len(parsed["threats"]) == 1
        assert parsed["threats"][0]["estimated_position_2d"] is None


def test_quest_threat_disappearance_and_expiration():
    """
    Verify that when an AP ages beyond stale_ap_ttl_ms, it is removed from the threat list
    allowing Unity ThreatVisualizationManager to remove the GameObject cleanly.
    """
    pipeline.reset()
    base_time = 2000000

    # Ingest threat at base_time
    pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[
                SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=-50, channel=1)
            ],
        ),
        received_at_ms=base_time,
    )
    state = pipeline.generate_threat_state(current_time_ms=base_time)
    assert len(state.threats) == 1

    # At base_time + 10s: still active
    state_mid = pipeline.generate_threat_state(current_time_ms=base_time + 10000)
    assert len(state_mid.threats) == 1

    # At base_time + 35s (> 20s TTL): threat disappears cleanly
    state_expired = pipeline.generate_threat_state(current_time_ms=base_time + 35000)
    assert len(state_expired.threats) == 0
    assert len(state_expired.active_threats) == 0

