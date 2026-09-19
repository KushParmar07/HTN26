"""Tests for observation and threat data models."""

import pytest
from pydantic import ValidationError

from backend.app.models.observation import (
    PodObservationBatch,
    SingleObservation,
    normalize_bssid,
)
from backend.app.models.threat import (
    EvidenceFlag,
    Position2D,
    SensorNodeInfo,
    ThreatItem,
    ThreatStateResponse,
    ThreatStatus,
)


def test_normalize_bssid():
    assert normalize_bssid("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("AA-BB-CC-DD-EE-FF") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("aabb.ccdd.eeff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_bssid("de:ad:be:ef:00:01") == "DE:AD:BE:EF:00:01"

    with pytest.raises(ValueError):
        normalize_bssid("invalid_mac")

    with pytest.raises(ValueError):
        normalize_bssid("AA:BB:CC:DD:EE")  # only 5 bytes


def test_single_observation_validation():
    obs = SingleObservation(
        bssid="de-ad-be-ef-00-01",
        ssid="HTN-Secure",
        rssi=-65,
        channel=6,
        authmode="wpa2_psk",
    )
    assert obs.bssid == "DE:AD:BE:EF:00:01"
    assert obs.authmode == "WPA2_PSK"

    # Out of range RSSI
    with pytest.raises(ValidationError):
        SingleObservation(bssid="aa:bb:cc:dd:ee:ff", rssi=-150, channel=1)

    # Positive RSSI
    with pytest.raises(ValidationError):
        SingleObservation(bssid="aa:bb:cc:dd:ee:ff", rssi=10, channel=1)


def test_pod_observation_batch():
    batch = PodObservationBatch(
        pod_id="pod_a",
        timestamp_ms=1726729200000,
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
    assert batch.pod_id == "pod_a"
    assert len(batch.observations) == 1
    assert batch.observations[0].bssid == "00:11:22:33:44:55"


def test_threat_models_serialization():
    threat = ThreatItem(
        bssid="DE:AD:BE:EF:00:01",
        ssid="HTN-Secure",
        status=ThreatStatus.SUSPICIOUS_INFRASTRUCTURE,
        risk_score=85.0,
        evidence_flags=[EvidenceFlag.UNKNOWN_BSSID, EvidenceFlag.SECURITY_MISMATCH],
        estimated_position_2d=Position2D(x=1.85, y=1.20),
        uncertainty_radius_m=0.55,
        last_seen_ms=1726729205000,
        observed_by_pods=["pod_a", "pod_b", "pod_c"],
    )

    state = ThreatStateResponse(
        version="1.0",
        generated_at_ms=1726729205120,
        sensor_nodes=[
            SensorNodeInfo(pod_id="pod_a", x=0.0, y=0.0),
            SensorNodeInfo(pod_id="pod_b", x=4.0, y=0.0),
            SensorNodeInfo(pod_id="pod_c", x=2.0, y=3.5),
        ],
        threats=[threat],
    )

    d = state.model_dump()
    assert d["version"] == "1.0"
    assert len(d["threats"]) == 1
    assert d["threats"][0]["risk_score"] == 85.0
    assert d["threats"][0]["evidence_flags"] == ["UNKNOWN_BSSID", "SECURITY_MISMATCH"]
    assert d["threats"][0]["estimated_position_2d"] == {"x": 1.85, "y": 1.20}
