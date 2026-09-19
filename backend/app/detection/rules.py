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
        self, ap: APState, current_time_ms: int
    ) -> Tuple[ThreatStatus, float, List[EvidenceFlag]]:
        """
        Evaluate an observed AP against baseline rules.
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

        # If it matches the authorized SSID but has an unknown BSSID -> Evil Twin / Rogue AP candidate
        if is_matching_ssid and not is_known_bssid:
            flags.append(EvidenceFlag.UNKNOWN_BSSID)
            raw_score += self.weights.unknown_bssid

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

            bounded_score = max(0.0, min(100.0, raw_score))
            status = (
                ThreatStatus.SUSPICIOUS_INFRASTRUCTURE
                if bounded_score >= self.suspicious_threshold
                else ThreatStatus.MONITORED
            )
            return status, bounded_score, flags

        # Unrelated third-party AP (different SSID, unknown BSSID)
        # We monitor it neutrally; check if sudden appearance
        elapsed_ms = max(0, current_time_ms - ap.first_seen_ms)
        if elapsed_ms <= self.sudden_appearance_threshold_ms:
            flags.append(EvidenceFlag.SUDDEN_APPEARANCE)
            raw_score += (self.weights.sudden_appearance * 0.5)  # attenuated for non-matching SSIDs

        bounded_score = max(0.0, min(100.0, raw_score))
        return ThreatStatus.MONITORED, bounded_score, flags
