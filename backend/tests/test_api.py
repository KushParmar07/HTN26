"""Unit tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from backend.app.main import app, pipeline

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "pod_a" in data["configured_pods"]


def test_ingest_and_threats_flow():
    # Clear pipeline state
    pipeline.state_manager.aps.clear()

    # Ingest rogue AP from pod_a, pod_b, pod_c
    observations_a = {
        "pod_id": "pod_a",
        "observations": [
            {
                "bssid": "DE:AD:BE:EF:00:01",
                "ssid": "HTN-Secure",
                "rssi": -55,
                "channel": 1,
                "authmode": "OPEN",
            }
        ],
    }
    observations_b = {
        "pod_id": "pod_b",
        "observations": [
            {
                "bssid": "DE:AD:BE:EF:00:01",
                "ssid": "HTN-Secure",
                "rssi": -65,
                "channel": 1,
                "authmode": "OPEN",
            }
        ],
    }
    observations_c = {
        "pod_id": "pod_c",
        "observations": [
            {
                "bssid": "DE:AD:BE:EF:00:01",
                "ssid": "HTN-Secure",
                "rssi": -58,
                "channel": 1,
                "authmode": "OPEN",
            }
        ],
    }

    res_a = client.post("/api/ingest", json=observations_a)
    assert res_a.status_code == 200

    res_b = client.post("/api/ingest", json=observations_b)
    assert res_b.status_code == 200

    res_c = client.post("/api/ingest", json=observations_c)
    assert res_c.status_code == 200

    # Query active threats
    res_threats = client.get("/api/threats")
    assert res_threats.status_code == 200
    threats_data = res_threats.json()

    assert threats_data["version"] == "1.0"
    assert len(threats_data["threats"]) == 1

    threat = threats_data["threats"][0]
    assert threat["bssid"] == "DE:AD:BE:EF:00:01"
    assert threat["status"] == "SUSPICIOUS_INFRASTRUCTURE"
    assert "UNKNOWN_BSSID" in threat["evidence_flags"]
    assert "SECURITY_MISMATCH" in threat["evidence_flags"]
    assert threat["estimated_position_2d"] is not None
    assert "x" in threat["estimated_position_2d"]
    assert "y" in threat["estimated_position_2d"]
    assert threat["uncertainty_radius_m"] is not None

    # Query all APs
    res_aps = client.get("/api/aps")
    assert res_aps.status_code == 200
    aps_data = res_aps.json()
    assert len(aps_data) == 1
    assert aps_data[0]["bssid"] == "DE:AD:BE:EF:00:01"


def test_authorize_bssid_endpoint():
    """Verify dynamic BSSID authorization endpoint."""
    res_get = client.get("/api/authorize_bssid")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "authorized_bssids" in data

    res_post = client.post(
        "/api/authorize_bssid",
        json={"bssid": "aa:bb:cc:dd:ee:ff", "ssid": "AdrianPhone"},
    )
    assert res_post.status_code == 200
    res_data = res_post.json()
    assert "AA:BB:CC:DD:EE:FF" in res_data["authorized_bssids"]
    assert res_data["ssid"] == "AdrianPhone"

