"""Access Point state tracking per BSSID across distributed sensor pods."""

import time
from typing import Dict, List, Optional, Set
from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.state.filter import CompositeRssiFilter


class APState:
    """State of an observed physical transmitter identified by BSSID."""

    def __init__(
        self,
        bssid: str,
        ssid: str,
        initial_seen_ms: int,
        channel: int,
        authmode: str,
        median_window: int = 5,
        ema_alpha: float = 0.3,
    ):
        self.bssid = bssid
        self.ssid = ssid
        self.first_seen_ms = initial_seen_ms
        self.last_seen_ms = initial_seen_ms
        self.channels_seen: Set[int] = {channel}
        self.current_channel = channel
        self.authmode = authmode
        self.observation_count = 0

        # Filter settings
        self.median_window = median_window
        self.ema_alpha = ema_alpha

        # Per-pod tracking
        self.pod_filters: Dict[str, CompositeRssiFilter] = {}
        self.pod_last_rssi_raw: Dict[str, int] = {}
        self.pod_last_seen_ms: Dict[str, int] = {}

    def update_pod_observation(
        self, pod_id: str, obs: SingleObservation, received_at_ms: int
    ) -> None:
        """Update AP state with a single observation from a specific pod."""
        self.observation_count += 1
        self.last_seen_ms = max(self.last_seen_ms, received_at_ms)

        # Update SSID if previously empty
        if not self.ssid and obs.ssid:
            self.ssid = obs.ssid

        # Update channel & authmode
        self.current_channel = obs.channel
        self.channels_seen.add(obs.channel)
        if obs.authmode and obs.authmode != "UNKNOWN":
            self.authmode = obs.authmode

        # Update per-pod RSSI filter
        if pod_id not in self.pod_filters:
            self.pod_filters[pod_id] = CompositeRssiFilter(
                median_window=self.median_window, ema_alpha=self.ema_alpha
            )

        self.pod_last_rssi_raw[pod_id] = obs.rssi
        self.pod_last_seen_ms[pod_id] = received_at_ms
        self.pod_filters[pod_id].update(float(obs.rssi))

    def get_filtered_rssi(self, pod_id: str) -> Optional[float]:
        """Get the current smoothed RSSI value for a pod."""
        filt = self.pod_filters.get(pod_id)
        if filt is None:
            return None
        return filt.current_value

    def get_active_pods(self, now_ms: int, max_age_ms: int = 10000) -> List[str]:
        """Get list of pods that have observed this AP within max_age_ms."""
        active = []
        for pod_id, last_seen in self.pod_last_seen_ms.items():
            if (now_ms - last_seen) <= max_age_ms:
                active.append(pod_id)
        return sorted(active)


class APStateManager:
    """Manages the lifecycle and state of all observed BSSIDs."""

    def __init__(
        self,
        stale_ttl_ms: int = 30000,
        median_window: int = 5,
        ema_alpha: float = 0.3,
    ):
        self.stale_ttl_ms = stale_ttl_ms
        self.median_window = median_window
        self.ema_alpha = ema_alpha
        self.aps: Dict[str, APState] = {}

    def ingest_batch(
        self, batch: PodObservationBatch, received_at_ms: Optional[int] = None
    ) -> List[APState]:
        """Ingest a batch from a pod, creating or updating AP states."""
        now_ms = received_at_ms if received_at_ms is not None else int(time.time() * 1000)
        updated: List[APState] = []

        for obs in batch.observations:
            if obs.bssid not in self.aps:
                self.aps[obs.bssid] = APState(
                    bssid=obs.bssid,
                    ssid=obs.ssid,
                    initial_seen_ms=now_ms,
                    channel=obs.channel,
                    authmode=obs.authmode,
                    median_window=self.median_window,
                    ema_alpha=self.ema_alpha,
                )
            ap = self.aps[obs.bssid]
            ap.update_pod_observation(batch.pod_id, obs, now_ms)
            updated.append(ap)

        return updated

    def get_ap(self, bssid: str) -> Optional[APState]:
        return self.aps.get(bssid)

    def get_all_aps(self) -> List[APState]:
        return list(self.aps.values())

    def prune_stale(self, now_ms: Optional[int] = None) -> int:
        """Remove APs not seen within stale_ttl_ms. Returns count of pruned APs."""
        current_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        stale_keys = [
            bssid
            for bssid, state in self.aps.items()
            if (current_ms - state.last_seen_ms) > self.stale_ttl_ms
        ]
        for key in stale_keys:
            del self.aps[key]
        return len(stale_keys)
