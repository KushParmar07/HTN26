"""Comprehensive robustness and edge-case tests for the RF Threat Detection pipeline."""

import json
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import DEFAULT_CONFIG, SensorNodeConfig, SystemConfig
from backend.app.localization.multilateration import MultilaterationSolver2D, rssi_to_distance_m
from backend.app.main import app, pipeline
from backend.app.models.observation import (
    PodObservationBatch,
    SingleObservation,
    normalize_bssid,
)
from backend.app.models.threat import ThreatStateResponse, ThreatStatus
from backend.app.pipeline import BackendPipeline
from backend.app.state.filter import (
    CompositeRssiFilter,
    ExponentialMovingAverageFilter,
    RollingMedianFilter,
)


@pytest.fixture
def clean_pipeline():
    """Create a fresh isolated pipeline instance for each test."""
    return BackendPipeline(config=DEFAULT_CONFIG)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# 1. Observation Model & Data Ingestion Robustness
# =============================================================================

def test_bssid_normalization_edge_cases():
    assert normalize_bssid("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("AA-BB-CC-DD-EE-FF") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("aabb.ccdd.eeff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("6809475ca6f1") == "68:09:47:5C:A6:F1"

    for invalid in ["", "   ", "xyz", "12:34:56", "AA:BB:CC:DD:EE:FF:11", None, 12345]:
        with pytest.raises(ValueError):
            normalize_bssid(invalid)


def test_ssid_edge_cases():
    # None/null SSID defaults to empty string
    obs = SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid=None, rssi=-50, channel=1)
    assert obs.ssid == ""

    # Quotes and backslashes preserved safely
    weird_ssid = r'Hack"Net\Test'
    obs2 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid=weird_ssid, rssi=-50, channel=1)
    assert obs2.ssid == weird_ssid

    # UTF-8 and emoji SSIDs
    utf8_ssid = "Wi-Fi_Café_☕_5G"
    obs3 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid=utf8_ssid, rssi=-50, channel=1)
    assert obs3.ssid == utf8_ssid

    # Control characters (null byte stripped)
    obs4 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid="Evil\x00Network", rssi=-50, channel=1)
    assert "\x00" not in obs4.ssid

    # Excessively long SSID truncated to 128 characters safely
    long_ssid = "A" * 200
    obs5 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid=long_ssid, rssi=-50, channel=1)
    assert len(obs5.ssid) == 128


def test_rssi_and_channel_normalization():
    # Floating point string or float RSSI coerced cleanly
    obs1 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi="-65.4", channel="6")
    assert obs1.rssi == -65
    assert obs1.channel == 6

    # Valid boundary channels
    obs2 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi=-50, channel=1)
    assert obs2.channel == 1

    obs3 = SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi=-50, channel=165)
    assert obs3.channel == 165

    # Out of range channels
    with pytest.raises(ValidationError):
        SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi=-50, channel=0)

    with pytest.raises(ValidationError):
        SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi=-50, channel=200)


def test_authmode_normalization_edge_cases():
    for raw, expected in [
        ("open", "OPEN"),
        ("wpa2-psk", "WPA2_PSK"),
        (" WPA3_SAE ", "WPA3_SAE"),
        (None, "UNKNOWN"),
        ("", "UNKNOWN"),
        ("   ", "UNKNOWN"),
    ]:
        obs = SingleObservation(bssid="AA:BB:CC:DD:EE:01", rssi=-50, channel=1, authmode=raw)
        assert obs.authmode == expected


def test_batch_duplicate_bssid_deduplication():
    # Batch containing duplicate observations of the same BSSID with different RSSI
    batch = PodObservationBatch(
        pod_id="pod_a",
        observations=[
            SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid="Net1", rssi=-70, channel=1),
            SingleObservation(bssid="AA:BB:CC:DD:EE:01", ssid="Net1", rssi=-45, channel=1),  # Stronger
            SingleObservation(bssid="AA:BB:CC:DD:EE:02", ssid="Net2", rssi=-60, channel=6),
        ],
    )
    # Must deduplicate to 2 observations, keeping the stronger -45 dBm
    assert len(batch.observations) == 2
    bssid_map = {obs.bssid: obs for obs in batch.observations}
    assert bssid_map["AA:BB:CC:DD:EE:01"].rssi == -45
    assert bssid_map["AA:BB:CC:DD:EE:02"].rssi == -60


def test_empty_observation_batch(client):
    res = client.post("/api/ingest", json={"pod_id": "pod_a", "observations": []})
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"
    assert res.json()["count"] == 0


def test_pod_id_whitespace_and_case(client):
    res = client.post(
        "/api/ingest",
        json={
            "pod_id": "  POD_A  ",
            "observations": [
                {"bssid": "AA:BB:CC:DD:EE:01", "ssid": "Test", "rssi": -55, "channel": 1}
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["pod_id"] == "pod_a"


def test_missing_and_malformed_json(client):
    # Completely invalid JSON syntax
    res = client.post(
        "/api/ingest",
        content="not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code in [400, 422]

    # Missing required pod_id
    res2 = client.post("/api/ingest", json={"observations": []})
    assert res2.status_code == 422

    # Empty pod_id string
    res3 = client.post("/api/ingest", json={"pod_id": "", "observations": []})
    assert res3.status_code == 422


# =============================================================================
# 2. Filter & Numerical Robustness
# =============================================================================

def test_filters_reject_nan_and_inf():
    # Rolling Median
    rm = RollingMedianFilter(window_size=5)
    rm.update(-60.0)
    rm.update(float("nan"))
    rm.update(float("inf"))
    assert rm.current_value == pytest.approx(-60.0)

    # EMA
    ema = ExponentialMovingAverageFilter(alpha=0.3)
    ema.update(-60.0)
    ema.update(float("nan"))
    ema.update(float("-inf"))
    assert ema.current_value == pytest.approx(-60.0)

    # Composite
    comp = CompositeRssiFilter(median_window=5, ema_alpha=0.3)
    comp.update(-60.0)
    comp.update(float("nan"))
    assert comp.current_value == pytest.approx(-60.0)


def test_rssi_to_distance_numerical_stability():
    # Extremely negative RSSI (noise floor)
    d_far = rssi_to_distance_m(-150.0)
    assert np.isfinite(d_far)
    assert d_far <= 10000.0

    # Extremely positive RSSI
    d_close = rssi_to_distance_m(50.0)
    assert np.isfinite(d_close)
    assert d_close >= 0.001

    # NaN / Inf input
    assert rssi_to_distance_m(float("nan")) == 1.0
    assert rssi_to_distance_m(float("inf")) == 1.0


# =============================================================================
# 3. Multilateration Geometry & Pod Counts
# =============================================================================

def test_multilateration_insufficient_pods():
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5),
    ]
    solver = MultilaterationSolver2D(sensors)

    # 0 pods
    pos, unc = solver.solve({})
    assert pos is None and unc is None

    # 1 pod
    pos, unc = solver.solve({"pod_a": -50.0})
    assert pos is None and unc is None

    # 2 pods
    pos, unc = solver.solve({"pod_a": -50.0, "pod_b": -60.0})
    assert pos is None and unc is None


def test_multilateration_four_pods():
    # 4 sensors in a square
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=4.0, y=4.0),
        SensorNodeConfig(pod_id="pod_d", x=0.0, y=4.0),
    ]
    solver = MultilaterationSolver2D(sensors)

    target_x, target_y = 2.0, 2.0
    rssi_map = {}
    for s in sensors:
        dist = np.sqrt((target_x - s.x) ** 2 + (target_y - s.y) ** 2)
        rssi_map[s.pod_id] = float(-45.0 - 10.0 * 2.7 * np.log10(dist))

    pos, unc = solver.solve(rssi_map)
    assert pos is not None
    assert pos.x == pytest.approx(2.0, abs=0.1)
    assert pos.y == pytest.approx(2.0, abs=0.1)
    assert unc is not None and unc > 0


def test_multilateration_collinear_pods():
    # 3 collinear pods along X axis (degenerate geometry)
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=2.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=4.0, y=0.0),
    ]
    solver = MultilaterationSolver2D(sensors)
    pos, unc = solver.solve({"pod_a": -55.0, "pod_b": -50.0, "pod_c": -55.0})

    # Must not throw, must produce finite output
    assert pos is not None
    assert np.isfinite(pos.x) and np.isfinite(pos.y)
    assert np.isfinite(unc) and unc > 0


# =============================================================================
# 4. End-to-End Pipeline State & Threat Lifecycle
# =============================================================================

def test_timestamp_uptime_vs_epoch_resilience(clean_pipeline):
    # Send batch with ESP32 uptime ms (e.g. 15000 ms)
    # Backend must not treat it as Unix epoch 1970 and immediately prune it!
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            timestamp_ms=15000,
            observations=[
                SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=-55, channel=1)
            ],
        )
    )
    # Threat state must retain this AP
    state = clean_pipeline.generate_threat_state()
    assert len(state.threats) == 1
    assert state.threats[0].bssid == "DE:AD:BE:EF:00:01"


def test_ap_pruning_and_reappearance(clean_pipeline):
    base_time = 1726729200000

    # Ingest at t=0
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[
                SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=-55, channel=1)
            ],
        ),
        received_at_ms=base_time,
    )
    assert len(clean_pipeline.state_manager.get_all_aps()) == 1

    # At t=35s (> stale_ttl_ms of 30s), AP should be pruned
    clean_pipeline.generate_threat_state(current_time_ms=base_time + 35000)
    assert len(clean_pipeline.state_manager.get_all_aps()) == 0

    # AP reappears at t=40s
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[
                SingleObservation(bssid="DE:AD:BE:EF:00:01", ssid="HTN-Secure", rssi=-55, channel=1)
            ],
        ),
        received_at_ms=base_time + 40000,
    )
    assert len(clean_pipeline.state_manager.get_all_aps()) == 1


def test_large_batch_ingestion(clean_pipeline):
    # Simulate a noisy conference environment with 100 APs
    observations = [
        SingleObservation(
            bssid=f"00:11:22:33:44:{i:02X}",
            ssid=f"Network_{i}",
            rssi=-40 - (i % 50),
            channel=(i % 11) + 1,
            authmode="WPA2_PSK" if i % 2 == 0 else "OPEN",
        )
        for i in range(100)
    ]
    batch = PodObservationBatch(pod_id="pod_a", observations=observations)

    t0 = time.time()
    clean_pipeline.ingest(batch)
    state = clean_pipeline.generate_threat_state()
    duration = time.time() - t0

    assert len(clean_pipeline.state_manager.get_all_aps()) == 100
    assert duration < 0.2  # Must process 100 APs in under 200 ms


def test_threat_state_json_strictness(clean_pipeline):
    # Ensure ThreatStateResponse produces strict, valid JSON with NO NaNs
    state = clean_pipeline.generate_threat_state()
    raw_json = state.model_dump_json()

    # Must be valid standard JSON
    parsed = json.loads(raw_json)
    assert "version" in parsed
    assert "threats" in parsed
    assert "active_threats" in parsed
    assert "sensor_nodes" in parsed
    assert "NaN" not in raw_json
    assert "Infinity" not in raw_json


# =============================================================================
# 5. WebSocket Endpoint Resilience
# =============================================================================

def test_websocket_immediate_state_and_ping(client):
    with client.websocket_connect("/ws/threats") as ws:
        # Client immediately receives initial threat state
        data = ws.receive_text()
        parsed = json.loads(data)
        assert parsed["version"] == "1.0"
        assert "threats" in parsed

        # Send ping, verify pong
        ws.send_text("ping")
        pong = json.loads(ws.receive_text())
        assert pong.get("type") == "pong"


# =============================================================================
# 6. Pod Lifecycle: Connect, Disconnect, Reconnect & Multi-Pod Transitions
# =============================================================================

def test_pod_connect_disconnect_reconnect_and_pod_transitions(clean_pipeline):
    """
    Test 1-pod, 2-pod, and 3-pod transitions:
    - 1 pod: threat detected, but localization unavailable (None, None)
    - 2 pods: threat detected, localization still unavailable (< 3 pods)
    - 3 pods: multilateration solves valid 2D coordinates & uncertainty
    - 1 pod drops (disconnect): spatial TTL expires, position resets to None
    - Pod reconnects: multilateration resumes smoothly
    """
    bssid = "DE:AD:BE:EF:00:01"
    ssid = "HTN-Secure"
    base_time = 1000000

    # Step 1: Pod A only (1 pod active)
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-50, channel=1)],
        ),
        received_at_ms=base_time,
    )
    state = clean_pipeline.generate_threat_state(current_time_ms=base_time)
    assert len(state.threats) == 1
    threat = state.threats[0]
    assert threat.status == ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
    assert threat.observed_by_pods == ["pod_a"]
    assert threat.estimated_position_2d is None
    assert threat.uncertainty_radius_m is None

    # Step 2: Pod B joins (2 pods active)
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_b",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-60, channel=1)],
        ),
        received_at_ms=base_time + 1000,
    )
    state = clean_pipeline.generate_threat_state(current_time_ms=base_time + 1000)
    threat = state.threats[0]
    assert sorted(threat.observed_by_pods) == ["pod_a", "pod_b"]
    assert threat.estimated_position_2d is None
    assert threat.uncertainty_radius_m is None

    # Step 3: Pod C joins (3 pods active -> Multilateration active!)
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_c",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-55, channel=1)],
        ),
        received_at_ms=base_time + 2000,
    )
    state = clean_pipeline.generate_threat_state(current_time_ms=base_time + 2000)
    threat = state.threats[0]
    assert sorted(threat.observed_by_pods) == ["pod_a", "pod_b", "pod_c"]
    assert threat.estimated_position_2d is not None
    assert threat.uncertainty_radius_m is not None
    assert threat.uncertainty_radius_m >= 0.3

    # Step 4: Pod C disconnects (no data beyond the configured 20s pod window)
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-50, channel=1)],
        ),
        received_at_ms=base_time + 15000,
    )
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_b",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-60, channel=1)],
        ),
        received_at_ms=base_time + 15000,
    )
    # Beyond 15s spatial TTL, estimated position clears cleanly
    state = clean_pipeline.generate_threat_state(current_time_ms=base_time + 23001)
    threat = state.threats[0]
    assert "pod_c" not in threat.observed_by_pods
    assert threat.estimated_position_2d is None
    assert threat.uncertainty_radius_m is None

    # Step 5: Pod C reconnects
    clean_pipeline.ingest(
        PodObservationBatch(
            pod_id="pod_c",
            observations=[SingleObservation(bssid=bssid, ssid=ssid, rssi=-55, channel=1)],
        ),
        received_at_ms=base_time + 24000,
    )
    state = clean_pipeline.generate_threat_state(current_time_ms=base_time + 24000)
    threat = state.threats[0]
    assert "pod_c" in threat.observed_by_pods
    assert threat.estimated_position_2d is not None


def test_concurrent_pod_ingestion_thread_safety(client):
    """Verify rapid concurrent ingestion from multiple pods does not corrupt backend state."""
    import concurrent.futures

    def post_batch(pod_id, i):
        payload = {
            "pod_id": pod_id,
            "observations": [
                {
                    "bssid": f"00:11:22:33:44:{i % 10:02X}",
                    "ssid": f"Network_{i % 10}",
                    "rssi": -40 - (i % 30),
                    "channel": 1,
                    "authmode": "WPA2_PSK",
                }
            ],
        }
        return client.post("/api/ingest", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        for i in range(30):
            futures.append(executor.submit(post_batch, "pod_a", i))
            futures.append(executor.submit(post_batch, "pod_b", i))
            futures.append(executor.submit(post_batch, "pod_c", i))
        for f in concurrent.futures.as_completed(futures):
            resp = f.result()
            assert resp.status_code == 200
            assert resp.json()["status"] == "accepted"


def test_websocket_rapid_reconnect_and_broadcast(client):
    """Test rapid sequential WebSocket connects and disconnects while ingest is active."""
    for _ in range(5):
        with client.websocket_connect("/ws/threats") as ws:
            data = ws.receive_text()
            assert "version" in data
            # Ingest during connection
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
                        }
                    ],
                },
            )
            update = ws.receive_text()
            assert "DE:AD:BE:EF:00:01" in update
        # Socket context exits, disconnecting cleanly


def test_backend_restart_simulation():
    """
    Simulate backend restart while pods are transmitting:
    A new pipeline instance starts clean, receives pod data, and re-establishes state immediately.
    """
    p1 = BackendPipeline(config=DEFAULT_CONFIG)
    p1.ingest(
        PodObservationBatch(
            pod_id="pod_a",
            observations=[
                SingleObservation(bssid="AA:BB:CC:DD:EE:FF", ssid="OldNet", rssi=-60, channel=6)
            ],
        )
    )
    assert len(p1.state_manager.get_all_aps()) == 1

    # Restart: instantiate fresh p2
    p2 = BackendPipeline(config=DEFAULT_CONFIG)
    assert len(p2.state_manager.get_all_aps()) == 0

    # Pods continue transmitting immediately into restarted pipeline
    p2.ingest(
        PodObservationBatch(
            pod_id="pod_b",
            observations=[
                SingleObservation(bssid="AA:BB:CC:DD:EE:FF", ssid="OldNet", rssi=-58, channel=6)
            ],
        )
    )
    assert len(p2.state_manager.get_all_aps()) == 1
    state = p2.generate_threat_state()
    assert state.version == "1.0"

