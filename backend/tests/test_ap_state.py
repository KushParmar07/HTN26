"""Unit tests for AP state management and multi-pod aggregation."""

from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.state.ap_state import APState, APStateManager


def test_ap_state_multi_pod_aggregation():
    manager = APStateManager(stale_ttl_ms=10000)

    # Pod A observes rogue AP
    batch_a = PodObservationBatch(
        pod_id="pod_a",
        observations=[
            SingleObservation(
                bssid="DE:AD:BE:EF:00:01",
                ssid="HTN-Secure",
                rssi=-50,
                channel=1,
                authmode="OPEN",
            )
        ],
    )
    manager.ingest_batch(batch_a, received_at_ms=1000)

    # Pod B observes the same rogue AP 200ms later
    batch_b = PodObservationBatch(
        pod_id="pod_b",
        observations=[
            SingleObservation(
                bssid="DE:AD:BE:EF:00:01",
                ssid="HTN-Secure",
                rssi=-65,
                channel=1,
                authmode="OPEN",
            )
        ],
    )
    manager.ingest_batch(batch_b, received_at_ms=1200)

    ap = manager.get_ap("DE:AD:BE:EF:00:01")
    assert ap is not None
    assert ap.first_seen_ms == 1000
    assert ap.last_seen_ms == 1200
    assert ap.observation_count == 2
    assert ap.get_filtered_rssi("pod_a") == -50.0
    assert ap.get_filtered_rssi("pod_b") == -65.0
    assert ap.get_active_pods(now_ms=1300, max_age_ms=1000) == ["pod_a", "pod_b"]


def test_ap_state_pruning():
    manager = APStateManager(stale_ttl_ms=5000)
    batch = PodObservationBatch(
        pod_id="pod_a",
        observations=[
            SingleObservation(
                bssid="00:11:22:33:44:55",
                ssid="HTN-Secure",
                rssi=-45,
                channel=6,
                authmode="WPA2_PSK",
            )
        ],
    )
    manager.ingest_batch(batch, received_at_ms=1000)

    assert len(manager.get_all_aps()) == 1

    # At t=5000, not stale yet
    pruned = manager.prune_stale(now_ms=5000)
    assert pruned == 0
    assert len(manager.get_all_aps()) == 1

    # At t=7000 (diff is 6000 > 5000), should prune
    pruned = manager.prune_stale(now_ms=7000)
    assert pruned == 1
    assert len(manager.get_all_aps()) == 0


def test_ap_state_position_history_and_velocity():
    from backend.app.models.threat import Position2D

    ap = APState(
        bssid="DE:AD:BE:EF:00:01",
        ssid="Test-Rogue",
        initial_seen_ms=1000,
        channel=6,
        authmode="OPEN",
        max_history_len=5,
    )

    # Initial position at t=1000
    pos1 = Position2D(x=0.0, y=0.0)
    ap.update_estimated_position(raw_pos=pos1, raw_uncertainty=1.0, now_ms=1000)
    assert len(ap.position_history) == 1
    assert ap.velocity_2d is None

    # Step to (2.0, 0.0) at t=2000
    pos2 = Position2D(x=2.0, y=0.0)
    ap.update_estimated_position(raw_pos=pos2, raw_uncertainty=1.0, now_ms=2000)
    assert len(ap.position_history) == 2
    assert ap.velocity_2d is not None
    assert ap.velocity_2d.movement_state == "MOVING"
    assert ap.velocity_2d.speed_mps > 0.15
    assert ap.velocity_2d.direction_deg is not None

    # Step 10 times to verify bounded deque length
    for i in range(3, 12):
        ap.update_estimated_position(
            raw_pos=Position2D(x=float(i), y=0.0),
            raw_uncertainty=1.0,
            now_ms=1000 * i,
        )
    assert len(ap.position_history) == 5
    assert len(ap.position_timestamps_ms) == 5

    # Test position expiration
    ap.update_estimated_position(
        raw_pos=None, raw_uncertainty=None, now_ms=1000 * 11 + 20000, pos_ttl_ms=15000
    )
    assert ap.estimated_pos is None
    assert ap.uncertainty_radius_m is None
    assert ap.velocity_2d is None

