"""Deterministic detection rules and explainable risk evaluation."""

from typing import List, Tuple
from backend.app.config import AuthorizedNetworkConfig, DetectionWeights
from backend.app.models.threat import EvidenceFlag, ThreatStatus
from backend.app.state.ap_state import APState


class DeterministicDetector:
    """Evaluates deterministic security rules against an AP's state and baseline."""

    def __init__(
        self,
        authorized: AuthorizedNetworkConfig,
        weights: DetectionWeights,
        suspicious_threshold: float = 40.0,
        sudden_appearance_threshold_ms: int = 60000,
    ):
        self.authorized = authorized
        self.weights = weights
        self.suspicious_threshold = suspicious_threshold
        self.sudden_appearance_threshold_ms = sudden_appearance_threshold_ms

    def evaluate(
        self,
        ap: APState,
        current_time_ms: int,
        all_aps: Optional[List[APState]] = None,
        active_pods: Optional[List[str]] = None,
    ) -> Tuple[ThreatStatus, float, List[EvidenceFlag]]:
        """
        Evaluate an observed AP against baseline rules and multi-sensor RF context.
        Returns: (ThreatStatus, bounded_risk_score, list_of_evidence_flags)
        """
        flags: List[EvidenceFlag] = []
        raw_score = 0.0

        is_matching_ssid = (ap.ssid == self.authorized.ssid) and (ap.ssid != "")
        is_known_bssid = ap.bssid in self.authorized.authorized_bssids

        # If it is the legitimate AP (correct SSID and known BSSID)
        if is_matching_ssid and is_known_bssid:
            # Check for sudden configuration tampering on known BSSID
            if ap.authmode != self.authorized.expected_authmode and ap.authmode != "UNKNOWN":
                flags.append(EvidenceFlag.SECURITY_MISMATCH)
                raw_score += self.weights.security_mismatch

            if ap.current_channel not in self.authorized.expected_channels:
                flags.append(EvidenceFlag.UNEXPECTED_CHANNEL)
                raw_score += self.weights.unexpected_channel

            status = (
                ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
                if raw_score >= self.suspicious_threshold
                else ThreatStatus.AUTHORIZED
            )
            bounded_score = max(0.0, min(100.0, raw_score))
            return status, bounded_score, flags

        # Check for duplicate SSID (another AP broadcasting the same SSID)
        is_duplicate_ssid = False
        if ap.ssid and all_aps:
            for other in all_aps:
                if other.bssid != ap.bssid and other.ssid == ap.ssid:
                    is_duplicate_ssid = True
                    break

        # If it matches the authorized SSID but has an unknown BSSID -> Evil Twin / Rogue AP candidate
        if is_matching_ssid and not is_known_bssid:
            flags.append(EvidenceFlag.UNKNOWN_BSSID)
            raw_score += self.weights.unknown_bssid

            if is_duplicate_ssid:
                flags.append(EvidenceFlag.DUPLICATE_SSID)
                raw_score += self.weights.duplicate_ssid

            # Check security mismatch
            if ap.authmode != self.authorized.expected_authmode:
                flags.append(EvidenceFlag.SECURITY_MISMATCH)
                raw_score += self.weights.security_mismatch

            # Check channel
            if ap.current_channel not in self.authorized.expected_channels:
                flags.append(EvidenceFlag.UNEXPECTED_CHANNEL)
                raw_score += self.weights.unexpected_channel

            # Check sudden appearance
            elapsed_ms = max(0, current_time_ms - ap.first_seen_ms)
            if elapsed_ms <= self.sudden_appearance_threshold_ms:
                flags.append(EvidenceFlag.SUDDEN_APPEARANCE)
                raw_score += self.weights.sudden_appearance

            # Check multiple sensors observing the rogue AP
            pods = active_pods if active_pods is not None else ap.get_active_pods(now_ms=current_time_ms)
            if len(pods) >= 2:
                flags.append(EvidenceFlag.MULTIPLE_SENSORS)
                raw_score += self.weights.multiple_sensors

            # Check strong RF signal presence (e.g. RSSI > -50 dBm on any pod)
            has_strong_signal = any(
                rssi is not None and rssi > -50.0
                for rssi in [ap.get_filtered_rssi(p) for p in pods]
            )
            if has_strong_signal:
                flags.append(EvidenceFlag.STRONG_SIGNAL)
                raw_score += self.weights.strong_signal

            bounded_score = max(0.0, min(100.0, raw_score))
            status = (
                ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
                if bounded_score >= self.suspicious_threshold
                else ThreatStatus.MONITORED
            )
            return status, bounded_score, flags

        # Unrelated third-party AP (different SSID, unknown BSSID)
        # Check if cloning another non-authorized network's SSID
        if is_duplicate_ssid:
            flags.append(EvidenceFlag.DUPLICATE_SSID)
            raw_score += self.weights.duplicate_ssid

        elapsed_ms = max(0, current_time_ms - ap.first_seen_ms)
        if elapsed_ms <= self.sudden_appearance_threshold_ms:
            flags.append(EvidenceFlag.SUDDEN_APPEARANCE)
            raw_score += (self.weights.sudden_appearance * 0.5)

        bounded_score = max(0.0, min(100.0, raw_score))
        status = (
            ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
            if bounded_score >= self.suspicious_threshold
            else ThreatStatus.MONITORED
        )
        return status, bounded_score, flags
