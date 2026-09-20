from fastapi.testclient import TestClient

from backend.app.main import app, pipeline
from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.pipeline import BackendPipeline


def ingest_source(target, ssid="Phone Trial", now=100000, pods=3):
    for pod in ["pod_a", "pod_b", "pod_c"][:pods]:
        target.ingest(PodObservationBatch(pod_id=pod, observations=[SingleObservation(
            bssid="AA:BB:CC:DD:EE:01", ssid=ssid, rssi=-55, channel=1, authmode="OPEN"
        )]), received_at_ms=now)


def test_monitored_sources_localization_promotion_and_expiry():
    target = BackendPipeline()
    ingest_source(target, pods=1)
    state = target.generate_threat_state(100001)
    assert not state.threats
    assert len(state.monitored_aps) == 1
    assert state.monitored_aps[0].estimated_position_2d is None
    ingest_source(target)
    state = target.generate_threat_state(100002)
    source = state.monitored_aps[0]
    assert source.estimated_position_2d is not None
    assert len(source.observed_by_pods) == 3
    # Same BSSID crossing the configured baseline retains identity, appears once.
    target.state_manager.get_ap(source.bssid).ssid = "HTN-Secure"
    state = target.generate_threat_state(100003)
    assert not state.monitored_aps
    assert state.threats[0].threat_id == source.threat_id
    assert state.active_threats == state.threats
    state = target.generate_threat_state(130000)
    assert not state.threats and not state.monitored_aps


def test_staggered_real_pod_cycles_share_localization_window():
    target = BackendPipeline()
    for pod, received_at in zip(
        ["pod_a", "pod_b", "pod_c"], [100000, 108000, 116000]
    ):
        target.ingest(
            PodObservationBatch(
                pod_id=pod,
                observations=[
                    SingleObservation(
                        bssid="AA:BB:CC:DD:EE:02",
                        ssid="AdrianPhone",
                        rssi=-42,
                        channel=6,
                        authmode="WPA2_PSK",
                    )
                ],
            ),
            received_at_ms=received_at,
        )

    state = target.generate_threat_state(116001)
    source = (state.threats + state.monitored_aps)[0]
    assert source.observed_by_pods == ["pod_a", "pod_b", "pod_c"]
    assert source.estimated_position_2d is not None


def test_monitored_sources_in_rest_and_websocket():
    pipeline.reset()
    try:
        import time
        ingest_source(pipeline, now=int(time.time() * 1000))
        with TestClient(app) as client:
            state = client.get("/api/threats").json()
            assert state["threats"] == state["active_threats"] == []
            assert len(state["monitored_aps"]) == 1
            with client.websocket_connect("/ws/threats") as ws:
                streamed = ws.receive_json()
                assert streamed["monitored_aps"][0]["bssid"] == "AA:BB:CC:DD:EE:01"
                assert streamed["monitored_aps"][0]["estimated_position_2d"] is not None
    finally:
        pipeline.reset()
