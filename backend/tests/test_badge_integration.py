"""Automated tests for MOBILE Hacker Badge RF scanner node integration."""

from fastapi.testclient import TestClient
from backend.app.config import SensorNodeConfig, SensorNodeType, SystemConfig
from backend.app.localization.multilateration import MultilaterationSolver2D
from backend.app.main import app, pipeline
from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.models.threat import EvidenceFlag, ThreatStatus

client = TestClient(app)


def test_mobile_sensor_solver_exclusion():
    """Verify MultilaterationSolver2D strictly excludes MOBILE nodes from spatial anchors."""
    nodes = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0, node_type=SensorNodeType.FIXED),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0, node_type=SensorNodeType.FIXED),
        SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5, node_type=SensorNodeType.FIXED),
        SensorNodeConfig(pod_id="badge_01", x=1.0, y=1.0, node_type=SensorNodeType.MOBILE),
    ]
    solver = MultilaterationSolver2D(sensor_nodes=nodes)

    # Solver should only register the 3 fixed anchors
    assert "pod_a" in solver.sensor_nodes
    assert "pod_b" in solver.sensor_nodes
    assert "pod_c" in solver.sensor_nodes
    assert "badge_01" not in solver.sensor_nodes

    # If only 2 fixed pods and 1 mobile badge report RSSI -> Insufficient fixed anchors (< 3)
    pos, unc = solver.solve({"pod_a": -50.0, "pod_b": -55.0, "badge_01": -40.0})
    assert pos is None
    assert unc is None

    # When 3 fixed pods report -> Solves cleanly, completely ignoring badge_01
    pos_fixed, unc_fixed = solver.solve({"pod_a": -50.0, "pod_b": -55.0, "pod_c": -60.0})
    pos_with_badge, unc_with_badge = solver.solve({
        "pod_a": -50.0,
        "pod_b": -55.0,
        "pod_c": -60.0,
        "badge_01": -30.0,  # strong fluctuating mobile RSSI
    })
    assert pos_fixed is not None
    assert pos_with_badge is not None
    # Position must be identical because badge_01 is ignored
    assert pos_fixed.x == pos_with_badge.x
    assert pos_fixed.y == pos_with_badge.y
    assert unc_fixed == unc_with_badge


def test_badge_ingestion_and_threat_state():
    """Verify badge observations ingest via HTTP API and report as MOBILE."""
    pipeline.reset()
    t_now = 5000000

    # Ingest from badge_01
    badge_batch = PodObservationBatch(
        pod_id="badge_01",
        timestamp_ms=t_now,
        observations=[
            SingleObservation(
                bssid="DE:AD:BE:EF:00:01",
                ssid="HTN-Secure",  # Evil twin rogue candidate
                rssi=-48,
                channel=1,
                authmode="OPEN",
            )
        ],
    )
    resp = client.post("/api/ingest", json=badge_batch.model_dump())
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["pod_id"] == "badge_01"

    # Query threat state
    state_res = client.get("/api/threats")
    assert state_res.status_code == 200
    data = state_res.json()

    # Verify badge appears dynamically in sensor_nodes as MOBILE
    node_ids = {n["pod_id"]: n["node_type"] for n in data["sensor_nodes"]}
    assert "pod_a" in node_ids and node_ids["pod_a"] == "fixed"
    assert "pod_b" in node_ids and node_ids["pod_b"] == "fixed"
    assert "pod_c" in node_ids and node_ids["pod_c"] == "fixed"
    assert "badge_01" in node_ids and node_ids["badge_01"] == "mobile"

    # Threat item should show badge_01 in observed_by_pods
    assert len(data["threats"]) == 1
    threat = data["threats"][0]
    assert threat["bssid"] == "DE:AD:BE:EF:00:01"
    assert "badge_01" in threat["observed_by_pods"]
    assert threat["filtered_rssi_by_pod"]["badge_01"] == -48.0
    # Position must be None because only badge_01 (0 fixed pods) has observed it
    assert threat["estimated_position_2d"] is None


def test_badge_and_fixed_pods_corroboration():
    """Verify badge provides multi-sensor corroboration without breaking fixed localization."""
    pipeline.reset()
    t_now = 6000000

    # 3 fixed pods observe rogue AP
    for pid, rssi in [("pod_a", -50), ("pod_b", -60), ("pod_c", -55)]:
        pipeline.ingest(
            PodObservationBatch(
                pod_id=pid,
                timestamp_ms=t_now,
                observations=[
                    SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=rssi, channel=1)
                ],
            ),
            received_at_ms=t_now,
        )

    # Badge also observes rogue AP
    pipeline.ingest(
        PodObservationBatch(
            pod_id="badge_01",
            timestamp_ms=t_now + 100,
            observations=[
                SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=-42, channel=1)
            ],
        ),
        received_at_ms=t_now + 100,
    )

    state = pipeline.generate_threat_state(current_time_ms=t_now + 200)
    assert len(state.threats) == 1
    threat = state.threats[0]

    # Localization must be computed from the 3 fixed pods
    assert threat.estimated_position_2d is not None
    assert threat.uncertainty_radius_m is not None

    # Corroborating evidence flags
    assert EvidenceFlag.MULTIPLE_SENSORS in threat.evidence_flags
    assert EvidenceFlag.STRONG_SIGNAL in threat.evidence_flags
    assert set(threat.observed_by_pods) == {"pod_a", "pod_b", "pod_c", "badge_01"}
    assert "badge_01" in threat.filtered_rssi_by_pod


def test_badge_websocket_streaming():
    """Verify WebSocket stream receives live badge updates."""
    pipeline.reset()
    t_now = 7000000

    with client.websocket_connect("/ws/threats") as ws:
        init_frame = ws.receive_json()
        assert "sensor_nodes" in init_frame

        # Ingest badge observation
        client.post(
            "/api/ingest",
            json=PodObservationBatch(
                pod_id="badge_01",
                timestamp_ms=t_now,
                observations=[
                    SingleObservation(bssid="AA:BB:CC:DD:EE:FF", ssid="HTN-Secure", rssi=-55, channel=1)
                ],
            ).model_dump(),
        )

        update_frame = ws.receive_json()
        nodes = {n["pod_id"]: n["node_type"] for n in update_frame["sensor_nodes"]}
        assert "badge_01" in nodes
        assert nodes["badge_01"] == "mobile"
        assert len(update_frame["threats"]) == 1
        assert "badge_01" in update_frame["threats"][0]["observed_by_pods"]
