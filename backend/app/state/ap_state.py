from collections import deque
import math
import time
from typing import Deque, Dict, List, Optional, Set, Tuple
from backend.app.models.observation import PodObservationBatch, SingleObservation
from backend.app.models.threat import Position2D, Velocity2D
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
        spatial_ema_alpha: float = 0.35,
        max_history_len: int = 20,
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
        self.spatial_ema_alpha = spatial_ema_alpha
        self.max_history_len = max_history_len

        # Per-pod tracking
        self.pod_filters: Dict[str, CompositeRssiFilter] = {}
        self.pod_last_rssi_raw: Dict[str, int] = {}
        self.pod_last_seen_ms: Dict[str, int] = {}

        # Smoothed 2D spatial tracking & movement
        self.estimated_pos: Optional[Position2D] = None
        self.uncertainty_radius_m: Optional[float] = None
        self.last_pos_update_ms: Optional[int] = None
        self.position_history: Deque[Position2D] = deque(maxlen=max_history_len)
        self.position_timestamps_ms: Deque[int] = deque(maxlen=max_history_len)
        self.velocity_2d: Optional[Velocity2D] = None

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

    def update_estimated_position(
        self,
        raw_pos: Optional[Position2D],
        raw_uncertainty: Optional[float],
        now_ms: Optional[int] = None,
        pos_ttl_ms: int = 15000,
    ) -> Tuple[Optional[Position2D], Optional[float]]:
        """
        Apply temporal exponential smoothing to 2D coordinates and uncertainty
        to eliminate high-frequency spatial jitter for VR rendering.
        Also derives 2D velocity vector, speed, heading, and movement state.
        If no fresh position is computed within pos_ttl_ms, clear the stale position.
        """
        current_time = now_ms if now_ms is not None else int(time.time() * 1000)

        if raw_pos is None:
            # Check if previous position has expired
            if self.last_pos_update_ms is not None and (current_time - self.last_pos_update_ms) > pos_ttl_ms:
                self.estimated_pos = None
                self.uncertainty_radius_m = None
                self.velocity_2d = None
            return self.estimated_pos, self.uncertainty_radius_m

        prev_pos = self.estimated_pos
        prev_time = self.position_timestamps_ms[-1] if self.position_timestamps_ms else None
        self.last_pos_update_ms = current_time

        if self.estimated_pos is None or self.uncertainty_radius_m is None:
            self.estimated_pos = raw_pos
            self.uncertainty_radius_m = raw_uncertainty
        else:
            alpha = self.spatial_ema_alpha
            smooth_x = alpha * raw_pos.x + (1.0 - alpha) * self.estimated_pos.x
            smooth_y = alpha * raw_pos.y + (1.0 - alpha) * self.estimated_pos.y
            self.estimated_pos = Position2D(x=round(smooth_x, 3), y=round(smooth_y, 3))

            if raw_uncertainty is not None:
                smooth_u = alpha * raw_uncertainty + (1.0 - alpha) * self.uncertainty_radius_m
                self.uncertainty_radius_m = round(smooth_u, 3)

        # Update bounded position history
        self.position_history.append(self.estimated_pos)
        self.position_timestamps_ms.append(current_time)

        # Compute velocity if we have a previous position and sensible delta t
        if prev_pos is not None and prev_time is not None:
            dt_s = (current_time - prev_time) / 1000.0
            if 0.1 <= dt_s <= 10.0:
                dx = self.estimated_pos.x - prev_pos.x
                dy = self.estimated_pos.y - prev_pos.y
                inst_vx = dx / dt_s
                inst_vy = dy / dt_s
                inst_speed = math.hypot(inst_vx, inst_vy)

                if self.velocity_2d is not None:
                    v_alpha = 0.4
                    vx = v_alpha * inst_vx + (1.0 - v_alpha) * self.velocity_2d.vx
                    vy = v_alpha * inst_vy + (1.0 - v_alpha) * self.velocity_2d.vy
                    speed = math.hypot(vx, vy)
                else:
                    vx = inst_vx
                    vy = inst_vy
                    speed = inst_speed

                if speed > 0.15:
                    movement_state = "MOVING"
                    direction_deg = round((math.degrees(math.atan2(vy, vx))) % 360.0, 1)
                else:
                    movement_state = "STATIONARY"
                    direction_deg = None

                self.velocity_2d = Velocity2D(
                    vx=round(vx, 3),
                    vy=round(vy, 3),
                    speed_mps=round(speed, 3),
                    direction_deg=direction_deg,
                    movement_state=movement_state,
                )
            elif dt_s > 10.0:
                self.velocity_2d = None

        return self.estimated_pos, self.uncertainty_radius_m

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
            if abs(now_ms - last_seen) <= max_age_ms:
                active.append(pod_id)
        return sorted(active)


class APStateManager:
    """Manages the lifecycle and state of all observed BSSIDs."""

    def __init__(
        self,
        stale_ttl_ms: int = 30000,
        median_window: int = 5,
        ema_alpha: float = 0.3,
        spatial_ema_alpha: float = 0.35,
    ):
        self.stale_ttl_ms = stale_ttl_ms
        self.median_window = median_window
        self.ema_alpha = ema_alpha
        self.spatial_ema_alpha = spatial_ema_alpha
        self.aps: Dict[str, APState] = {}

    def ingest_batch(
        self, batch: PodObservationBatch, received_at_ms: Optional[int] = None
    ) -> List[APState]:
        """Ingest a batch from a pod, creating or updating AP states."""
        now_ms = received_at_ms if received_at_ms is not None else int(time.time() * 1000)

        # Validate timestamp: if batch timestamp is missing, zero, or wildly out of sync
        # with server wall clock (e.g. ESP32 uptime ms), bind to server arrival time.
        effective_ts = now_ms
        if batch.timestamp_ms is not None and batch.timestamp_ms > 0:
            # If timestamp looks like a plausible epoch timestamp (within 5 minutes of server)
            if abs(now_ms - batch.timestamp_ms) < 300_000:
                effective_ts = batch.timestamp_ms

        updated: List[APState] = []

        for obs in batch.observations:
            if obs.bssid not in self.aps:
                self.aps[obs.bssid] = APState(
                    bssid=obs.bssid,
                    ssid=obs.ssid,
                    initial_seen_ms=effective_ts,
                    channel=obs.channel,
                    authmode=obs.authmode,
                    median_window=self.median_window,
                    ema_alpha=self.ema_alpha,
                    spatial_ema_alpha=self.spatial_ema_alpha,
                )
            ap = self.aps[obs.bssid]
            ap.update_pod_observation(batch.pod_id, obs, effective_ts)
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
