"""Unit tests for AP state management and multi-pod aggregation."""

from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.state.ap_state import APStateManager


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
