"""Unit tests for deterministic detection rules and risk scoring."""

from backend.app.config import AuthorizedNetworkConfig, DetectionWeights
from backend.app.detection.rules import DeterministicDetector
from backend.app.models.threat import EvidenceFlag, ThreatStatus
from backend.app.state.ap_state import APState


def test_authorized_ap_detection():
    auth_config = AuthorizedNetworkConfig(
        ssid="HTN-Secure",
        authorized_bssids={"00:11:22:33:44:55"},
        expected_authmode="WPA2_PSK",
        expected_channels={6},
    )
    detector = DeterministicDetector(
        authorized=auth_config,
        weights=DetectionWeights(),
        suspicious_threshold=40.0,
    )

    legit_ap = APState(
        bssid="00:11:22:33:44:55",
        ssid="HTN-Secure",
        initial_seen_ms=1000,
        channel=6,
        authmode="WPA2_PSK",
    )

    status, risk, flags = detector.evaluate(legit_ap, current_time_ms=5000)
    assert status == ThreatStatus.AUTHORIZED
    assert risk == 0.0
    assert len(flags) == 0


def test_rogue_evil_twin_ap_detection():
    auth_config = AuthorizedNetworkConfig(
        ssid="HTN-Secure",
        authorized_bssids={"00:11:22:33:44:55"},
        expected_authmode="WPA2_PSK",
        expected_channels={6},
    )
    detector = DeterministicDetector(
        authorized=auth_config,
        weights=DetectionWeights(
            unknown_bssid=50.0,
            security_mismatch=30.0,
            unexpected_channel=15.0,
            sudden_appearance=10.0,
        ),
        suspicious_threshold=40.0,
        sudden_appearance_threshold_ms=60000,
    )

    # Rogue AP: impersonates HTN-Secure, OPEN auth, Channel 1, unknown BSSID
    rogue_ap = APState(
        bssid="DE:AD:BE:EF:00:01",
        ssid="HTN-Secure",
        initial_seen_ms=10000,
        channel=1,
        authmode="OPEN",
    )

    status, risk, flags = detector.evaluate(rogue_ap, current_time_ms=15000)
    assert status == ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
    assert EvidenceFlag.UNKNOWN_BSSID in flags
    assert EvidenceFlag.SECURITY_MISMATCH in flags
    assert EvidenceFlag.UNEXPECTED_CHANNEL in flags
    assert EvidenceFlag.SUDDEN_APPEARANCE in flags
    # 50 + 30 + 15 + 10 = 105 -> bounded to 100
    assert risk == 100.0


def test_unrelated_third_party_ap():
    auth_config = AuthorizedNetworkConfig(ssid="HTN-Secure")
    detector = DeterministicDetector(
        authorized=auth_config,
        weights=DetectionWeights(),
        suspicious_threshold=40.0,
    )

    other_ap = APState(
        bssid="AA:BB:CC:11:22:33",
        ssid="Campus-Guest",
        initial_seen_ms=1000,
        channel=11,
        authmode="OPEN",
    )

    status, risk, flags = detector.evaluate(other_ap, current_time_ms=10000)
    assert status == ThreatStatus.MONITORED
    assert risk < 40.0


def test_duplicate_ssid_detection():
    auth_config = AuthorizedNetworkConfig(
        ssid="HTN-Secure",
        authorized_bssids={"00:11:22:33:44:55"},
    )
    detector = DeterministicDetector(
        authorized=auth_config,
        weights=DetectionWeights(),
        suspicious_threshold=40.0,
    )

    ap1 = APState(
        bssid="11:22:33:44:55:66",
        ssid="Guest-Wifi",
        initial_seen_ms=1000,
        channel=1,
        authmode="WPA2_PSK",
    )
    ap2 = APState(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="Guest-Wifi",
        initial_seen_ms=1000,
        channel=6,
        authmode="OPEN",
    )

    status, risk, flags = detector.evaluate(ap2, current_time_ms=5000, all_aps=[ap1, ap2])
    assert EvidenceFlag.DUPLICATE_SSID in flags


def test_multiple_sensors_and_strong_signal():
    from backend.app.models.observation import SingleObservation

    auth_config = AuthorizedNetworkConfig(
        ssid="HTN-Secure",
        authorized_bssids={"00:11:22:33:44:55"},
    )
    detector = DeterministicDetector(
        authorized=auth_config,
        weights=DetectionWeights(),
        suspicious_threshold=40.0,
    )

    ap = APState(
        bssid="AA:BB:CC:11:22:33",
        ssid="HTN-Secure",
        initial_seen_ms=1000,
        channel=1,
        authmode="OPEN",
    )
    obs = SingleObservation(bssid="AA:BB:CC:11:22:33", ssid="HTN-Secure", rssi=-42, channel=1, authmode="OPEN")
    ap.update_pod_observation("pod_a", obs, 2000)
    ap.update_pod_observation("pod_b", obs, 2000)

    status, risk, flags = detector.evaluate(
        ap, current_time_ms=5000, active_pods=["pod_a", "pod_b"]
    )
    assert EvidenceFlag.MULTIPLE_SENSORS in flags
    assert EvidenceFlag.STRONG_SIGNAL in flags
